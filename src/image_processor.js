// =======================
// IMPORTS E COSTANTI
// =======================
const fs = require('fs').promises;
const path = require('path');
const os = require('os');
const {
  convertWorker,
  createThumbnailWorker
} = require('./worker_forks');
const { cropWorker } = require('./workers/crop_worker');
const { getAllFolders } = require('./scripts/utils');
const EXCLUDED_FOLDERS = require('./scripts/excluded_folders'); // <-- aggiungi questa riga

module.exports = { processDir };

// Numero massimo di processi paralleli per batch processing
const total = os.cpus().length;
const MAX_PARALLEL = total > 4 ? total - 1 : Math.max(1, Math.floor(total / 2));

// Profili delle thumbnails generate
const THUMBNAIL_ALIASES = {
  low_quality: { size: [640, 480], quality: 75, crop: false, format: 'webp' },
  gallery:     { size: [1920,1080], quality: 75, crop: false, format: 'webp' }
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
async function processDir(
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
    folderInfo = { allFolders, currentFolderIdx: 0 };
    progressCallback({
      current: 0, total: 0,
      folderIdx: 0, folderTotal: allFolders.length,
      currentFolder: '', currentFile: ''
    });
    errorFiles = [];
  }

  folderInfo.currentFolderIdx =
    folderInfo.allFolders.findIndex(f => path.resolve(f) === path.resolve(dir)) + 1;

  const relativePath = path.relative(baseInput, dir);
  const outDir = path.join(baseOutput, relativePath);
  await fs.mkdir(outDir, { recursive: true });

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const dirs = entries.filter(e => e.isDirectory()).map(e => e.name);
  const images = entries
    .filter(e => !e.isDirectory() && /\.(tif|jpe?g|png)$/i.test(e.name))
    .map(e => e.name);
  const xmls = entries
    .filter(e => !e.isDirectory() && /\.xml$/i.test(e.name))
    .map(e => e.name);

  // =======================
  // RICORSIONE SU SOTTOCARTELLE
  // =======================
  for (const sub of dirs) {
    // Escludi le cartelle presenti in EXCLUDED_FOLDERS (case-insensitive)
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
  if (images.length) {
    let current = 0;

    // Prepara le directory per i crop e le thumbnails (una sola volta per cartella)
    const thumbsBaseCrop = path.join(baseOutput, 'thumbnails', relativePath);
    const thumbsBase = path.join(baseOutput, 'thumbnails', relativePath);
    await fs.mkdir(thumbsBaseCrop, { recursive: true });
    if (thumbsBase !== thumbsBaseCrop) {  // Se sono diversi, crea la cartella
      try {
        await fs.mkdir(thumbsBase, { recursive: true });
      } catch (e) {
        if (e.code !== 'EEXIST') throw e;
      }
    }

    // Crea una lista di task asincroni per ogni immagine
    const tasks = images.map(file => async () => {
      if (shouldStopFn()) return;
      const src = path.join(dir, file);
      const dest = path.join(outDir, file.replace(/\.\w+$/, '.webp'));
      let skip = false;
      try {
        // Se il file di destinazione esiste già e ha size > 0, salta la conversione
        if ((await fs.stat(dest)).size > 0) skip = true;
        else await fs.unlink(dest);
      } catch {}
      if (!skip) {
        try {
          // =======================
          // CONVERSIONE IMMAGINE IN WEBP
          // =======================
          await convertWorker(src, dest);

          // =======================
          // CROP (OPZIONALE) E GENERAZIONE BOOK.WEBP
          // =======================
          if (crop) {
            const cropJpgDest = path.join(
              thumbsBaseCrop,
              path.basename(dest, '.webp') + `_book.jpg`
            );
            const cropWebpDest = path.join(
              thumbsBaseCrop,
              path.basename(dest, '.webp') + `_book.webp`
            );
            await cropWorker(dest, cropJpgDest);

            // Usa il thumbnail worker per creare il book.webp con profilo gallery
            const galleryProfile = THUMBNAIL_ALIASES.gallery;
            await createThumbnailWorker(
              cropJpgDest,
              cropWebpDest,
              JSON.stringify(galleryProfile)
            );

            // Elimina il file JPG temporaneo dopo la conversione
            await fs.unlink(cropJpgDest);
          }
        } catch (e) {
          errorFiles.push(`${src} - ${e.message}`);
          return;
        }
      }

      // =======================
      // GENERAZIONE THUMBNAILS (PER OGNI ALIAS)
      // =======================
      for (const alias of Object.keys(THUMBNAIL_ALIASES)) {
        const thumbPath = path.join(
          thumbsBase,
          path.basename(dest, '.webp') + `_${alias}.webp`
        );
        try {
          await createThumbnailWorker(
            dest,
            thumbPath,
            JSON.stringify(THUMBNAIL_ALIASES[alias])
          );
        } catch (e) {
          errorFiles.push(`${dest} (${alias}) - ${e.message}`);
        }
      }

      // =======================
      // AGGIORNAMENTO PROGRESS
      // =======================
      current++;
      progressCallback({
        current,
        total: images.length,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
    });

    // =======================
    // ESECUZIONE TASKS IN BATCHES PARALLELI
    // =======================
    await processInBatches(tasks, MAX_PARALLEL);
  }

  // =======================
  // COPIA FILE XML (SE PRESENTI)
  // =======================
  for (const file of xmls) {
    if (shouldStopFn()) break;
    const src = path.join(dir, file);
    const dest = path.join(outDir, file);
    try {
      await fs.copyFile(src, dest);
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
