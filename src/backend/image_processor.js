// =======================
// IMPORTS E COSTANTI
// =======================
import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import { convertWorker, createThumbnailWorker } from './worker_forks.js';
import { cropWorker } from './workers/crop_worker.js';
import { getAllFolders } from './scripts/utils.js';
import EXCLUDED_FOLDERS from './scripts/excluded_folders.js';
import Logger from '../backend/Logger.js';

const logger = new Logger();

// Numero massimo di processi paralleli per batch processing
const total = os.cpus().length;
const MAX_PARALLEL = total > 4 ? total - 1 : Math.max(1, Math.floor(total / 2));

// Profili delle thumbnails generate
const THUMBNAIL_ALIASES = {
  low_quality:  { size: [640, 480],   quality: 75, crop: false, format: 'webp' },
  gallery:      { size: [1920, 1080], quality: 75, crop: false, format: 'webp' }
};

// =======================
// FUNZIONE DI BATCH PROCESSING
// =======================
/**
 * Esegue le funzioni asincrone in batches, limitando il numero di processi paralleli.
 * @param {Array<Function>} tasks - Array di funzioni async (ognuna ritorna una Promise)
 * @param {number} maxParallel - Numero massimo di task in parallelo
 * @returns {Promise<Array>} - Risultati delle Promise (settled)
 */
async function processInBatches(tasks, maxParallel) {
  const results = [];
  const queue = [...tasks];
  const running = [];

  while (queue.length || running.length) {
    while (running.length < maxParallel && queue.length) {
      const p = queue.shift()().finally(() => {
        running.splice(running.indexOf(p), 1);
      });
      running.push(p);
      results.push(p);
    }
    await Promise.race(running);
  }

  return Promise.allSettled(results);
}

// =======================
// FUNZIONE PRINCIPALE DI PROCESSING
// =======================
/**
 * Processa una directory di immagini (e sottocartelle), convertendo, croppando e generando thumbnails.
 * @param {string} dir - Directory da processare
 * @param {Function} progressCallback - Callback per aggiornamento avanzamento
 * @param {string} baseInput - Directory di input base (per path relativi)
 * @param {string} baseOutput - Directory di output base
 * @param {object|null} folderInfo - Info sulle cartelle (per progress)
 * @param {Function} shouldStopFn - Funzione che ritorna true se bisogna interrompere
 * @param {Array|null} errorFiles - Array dove accumulare errori
 * @param {boolean} isRoot - True se è la chiamata principale
 * @param {boolean} crop - Se true, esegue anche il crop delle immagini
 */
export async function processDir(
  dir,
  progressCallback = () => {},
  baseInput = dir,
  baseOutput = path.join(
    process.env.HOME || process.env.USERPROFILE,
    'output1',
    path.basename(baseInput)
  ),
  folderInfo = null,
  shouldStopFn = () => false,
  errorFiles = null,
  isRoot = true,
  crop = true
) {
  // =======================
  // INIZIALIZZAZIONE E SCANSIONE CARTELLE
  // =======================
  if (shouldStopFn()) return;

  if (!folderInfo) {
    const allFolders = await getAllFolders(baseInput);
    
    // Controlla se la cartella principale contiene immagini
    const mainFolderEntries = await fs.readdir(baseInput, { withFileTypes: true });
    const mainFolderImages = mainFolderEntries
      .filter(e => !e.isDirectory() && /\.(tif|jpe?g|png)$/i.test(e.name))
      .map(e => e.name);
    
    // Prepara lista cartelle da processare
    const foldersToProcess = [];
    
    // Aggiungi cartella principale se contiene immagini
    if (mainFolderImages.length > 0) {
      foldersToProcess.push({
        path: baseInput,
        name: `📁 Cartella principale (${path.basename(baseInput)})`,
        relativePath: '.',
        isMainFolder: true,
        status: 'pending',
        progress: 0,
        current: 0,
        total: 0
      });
    }
    
    // Aggiungi sottocartelle (escludendo la principale)
    const subFolders = allFolders.filter(folder => path.resolve(folder) !== path.resolve(baseInput));
    subFolders.forEach(folder => {
      foldersToProcess.push({
        path: folder,
        name: path.basename(folder),
        relativePath: path.relative(baseInput, folder),
        isMainFolder: false,
        status: 'pending',
        progress: 0,
        current: 0,
        total: 0
      });
    });
    
    folderInfo = { 
      allFolders: [baseInput, ...subFolders], // Include baseInput per il processing
      currentFolderIdx: 0,
      foldersStatus: foldersToProcess,
      hasSubfolders: foldersToProcess.length > 1, // Più di una cartella = caso misto o solo sottocartelle
      hasMainFolder: mainFolderImages.length > 0
    };
    
    // Emetti sempre l'inizializzazione
    progressCallback({
      type: 'folders_init',
      foldersStatus: folderInfo.foldersStatus,
      hasSubfolders: folderInfo.hasSubfolders,
      hasMainFolder: folderInfo.hasMainFolder,
      totalFolders: foldersToProcess.length,
      current: 0,
      total: 0,
      folderIdx: 0,
      folderTotal: foldersToProcess.length,
      currentFolder: '',
      currentFile: ''
    });
    errorFiles = [];
  }

  folderInfo.currentFolderIdx =
    folderInfo.allFolders.findIndex(f => path.resolve(f) === path.resolve(dir)) + 1;

  // Aggiorna stato cartella corrente nella foldersStatus
  const currentFolderStatus = folderInfo.foldersStatus.find(
    f => path.resolve(f.path) === path.resolve(dir)
  );
  if (currentFolderStatus) {
    currentFolderStatus.status = 'processing';
  }

  const relativePath = path.relative(baseInput, dir);
  const outDir = path.join(baseOutput, relativePath);
  await fs.mkdir(outDir, { recursive: true });

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const dirs   = entries.filter(e => e.isDirectory()).map(e => e.name);
  const images = entries
    .filter(e => !e.isDirectory() && /\.(tif|jpe?g|png)$/i.test(e.name))
    .map(e => e.name);
  const videos = entries
    .filter(e => !e.isDirectory() && /\.(mp4|mov|avi|mkv|webm|m4v)$/i.test(e.name))
    .map(e => e.name);
  const xmls   = entries
    .filter(e => !e.isDirectory() && /\.xml$/i.test(e.name))
    .map(e => e.name);

  // =======================
  // RICORSIONE SU SOTTOCARTELLE
  // =======================
  for (const sub of dirs) {
    if (
      shouldStopFn() ||
      EXCLUDED_FOLDERS.some(ex => ex.toLowerCase() === sub.toLowerCase())
    ) continue;

    await processDir(
      path.join(dir, sub),
      progressCallback,
      baseInput,
      baseOutput,
      folderInfo,
      shouldStopFn,
      errorFiles,
      false,
      crop
    );
  }

  // =======================
  // PROCESSING IMMAGINI NELLA CARTELLA CORRENTE
  // =======================
  logger.info(`Processing images in: ${dir}`);
  if (images.length) {
    logger.info(`Found ${images.length} images in: ${dir}`);
    let current = 0;

    // Aggiorna il totale per questa cartella
    if (currentFolderStatus) {
      currentFolderStatus.total = images.length;
      currentFolderStatus.current = 0;
    }

    const thumbsBaseCrop = path.join(baseOutput, 'thumbnails', relativePath);
    const thumbsBase     = path.join(baseOutput, 'thumbnails', relativePath);
    await fs.mkdir(thumbsBaseCrop, { recursive: true });
    if (thumbsBase !== thumbsBaseCrop) {
      try {
        await fs.mkdir(thumbsBase, { recursive: true });
      } catch (e) {
        if (e.code !== 'EEXIST') throw e;
      }
    }

    const tasks = images.map(file => async () => {
      if (shouldStopFn()) return;
      const src  = path.join(dir, file);
      const dest = path.join(outDir, file.replace(/\.\w+$/, '.webp'));
      let skip   = false;

      try {
        if ((await fs.stat(dest)).size > 0) skip = true;
        else await fs.unlink(dest);
      } catch {}

      if (!skip) {
        try {
          await convertWorker(src, dest);

          if (crop) {
            const cropJpgDest  = path.join(thumbsBaseCrop, `${path.basename(dest, '.webp')}_book.jpg`);
            const cropWebpDest = path.join(thumbsBaseCrop, `${path.basename(dest, '.webp')}_book.webp`);
            await cropWorker(dest, cropJpgDest);
            await createThumbnailWorker(cropJpgDest, cropWebpDest, JSON.stringify(THUMBNAIL_ALIASES.gallery));
            await fs.unlink(cropJpgDest);
          }
        } catch (e) {
          errorFiles.push(`${src} - ${e.message}`);
          return;
        }
      }

      for (const alias of Object.keys(THUMBNAIL_ALIASES)) {
        const thumbPath = path.join(thumbsBase, `${path.basename(dest, '.webp')}_${alias}.webp`);
        try {
          await createThumbnailWorker(dest, thumbPath, JSON.stringify(THUMBNAIL_ALIASES[alias]));
        } catch (e) {
          errorFiles.push(`${dest} (${alias}) - ${e.message}`);
        }
      }

      current++;
      
      // Aggiorna progress della cartella corrente
      if (currentFolderStatus) {
        currentFolderStatus.current = current;
        currentFolderStatus.progress = Math.floor((current / images.length) * 100);
      }
      
      progressCallback({
        type: folderInfo.hasSubfolders ? 'file_progress' : 'main_folder_progress',
        foldersStatus: folderInfo.foldersStatus,
        hasSubfolders: folderInfo.hasSubfolders,
        current,
        total: images.length,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
    });

    await processInBatches(tasks, MAX_PARALLEL);
    
    // Segna cartella come completata
    if (currentFolderStatus) {
      currentFolderStatus.status = 'completed';
      currentFolderStatus.progress = 100;
    }
  }

  // =======================
  // COPIA FILE XML (SE PRESENTI)
  // =======================
  for (const file of xmls) {
    if (shouldStopFn()) break;
    const src  = path.join(dir, file);
    const dest = path.join(outDir, file);
    try {
      await fs.copyFile(src, dest);
    } catch (e) {
      errorFiles.push(`${src} - ${e.message}`);
    }
  }

  // =======================
  // COPIA FILE VIDEO (SE PRESENTI)
  // =======================
  for (const file of videos) {
    if (shouldStopFn()) break;
    const src  = path.join(dir, file);
    const dest = path.join(outDir, file);
    try {
      await fs.copyFile(src, dest);
      logger.info(`Copied video: ${file}`);
    } catch (e) {
      errorFiles.push(`${src} - ${e.message}`);
    }
  }

  // =======================
  // SCRITTURA FILE DI ERRORI (SOLO ALLA FINE DEL ROOT)
  // =======================
  if (isRoot && errorFiles.length) {
    await fs.writeFile(
      path.join(baseOutput, 'error_files.txt'),
      errorFiles.join('\n')
    );
  }
}
