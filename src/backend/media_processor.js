// =======================
// IMPORTS E COSTANTI
// =======================
import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import {
  cropPageWorker,
  convertWorker,
  createThumbnailWorker
} from './worker_forks.js';
import {
  optimizeVideo,
  generateVideoThumbnails,
  extractVideoFrame,
  checkFFmpegAvailable
} from './workers/video_worker.js';
import { cropWorker } from './workers/crop_worker.js';
import { getAllFolders } from './scripts/utils.js';
import EXCLUDED_FOLDERS from './scripts/excluded_folders.js';
import Logger from './Logger.js';

const logger = new Logger();

// Numero massimo di processi paralleli per batch processing
const total = os.cpus().length;
const MAX_PARALLEL = 2 //total > 4 ? total - 1 : Math.max(1, Math.floor(total / 2));

// Profili delle thumbnails generate (Base - modificato da aggressivity)
const THUMBNAIL_ALIASES_BASE = {
  low_quality:  { size: [640, 480],   quality: 75, crop: false, format: 'webp' },
  gallery:      { size: [1920, 1080], quality: 75, crop: false, format: 'webp' }
};

// Profili di aggressività per qualità immagini
// Formula base: quality = Math.round(baseline - originalKB / divisor)
const AGGRESSIVITY_PROFILES = {
  low: {
    formulaBaseline: 95,      // Starts at higher quality
    formulaDivisor: 35,       // Slower quality decay with file size
    thumbnailQualityModifier: 10, // +10 to base quality
    description: 'Alta qualità, dimensioni maggiori'
  },
  standard: {
    formulaBaseline: 90,      // Current default
    formulaDivisor: 27.3,     // Current default
    thumbnailQualityModifier: 0, // no change
    description: 'Bilanciamento qualità/dimensioni'
  },
  high: {
    formulaBaseline: 80,      // Starts at lower quality
    formulaDivisor: 22,       // Faster quality decay with file size
    thumbnailQualityModifier: -15, // -15 to base quality
    description: 'File più piccoli, qualità ridotta'
  }
};

// Export per uso nei workers
export { AGGRESSIVITY_PROFILES };

// Funzione per ottenere i profili thumbnail con aggressività applicata
function getThumbnailAliases(aggressivity = 'standard') {
  const profile = AGGRESSIVITY_PROFILES[aggressivity] || AGGRESSIVITY_PROFILES.standard;
  const aliases = {};

  for (const [key, value] of Object.entries(THUMBNAIL_ALIASES_BASE)) {
    aliases[key] = {
      ...value,
      quality: Math.max(20, Math.min(100, value.quality + profile.thumbnailQualityModifier))
    };
  }

  return aliases;
}

// Profili di ottimizzazione video
const VIDEO_OPTIMIZATION_PROFILES = {
  web: {
    codec: 'libx264',
    crf: 23,
    preset: 'medium',
    maxWidth: 1920,
    maxHeight: 1080,
    audioBitrate: '128k',
    audioCodec: 'aac'
  },
  mobile: {
    codec: 'libx264',
    crf: 28,
    preset: 'fast',
    maxWidth: 1280,
    maxHeight: 720,
    audioBitrate: '96k',
    audioCodec: 'aac'
  },
  archive: {
    codec: 'libx265',
    crf: 28,
    preset: 'slow',
    maxWidth: 1920,
    maxHeight: 1080,
    audioBitrate: '128k',
    audioCodec: 'aac'
  }
};

// Profili thumbnail video
const VIDEO_THUMBNAIL_PROFILES = {
  preview: { timeOffset: '00:00:01', width: 640, height: 480, quality: 75 },
  poster: { timeOffset: '00:00:03', width: 1280, height: 720, quality: 85 }
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
 * @param {boolean} optimizeVideos - Se true, ottimizza i video invece di copiarli
 */
// Helper: Recursively count all images in a directory
async function countAllImages(dir) {
  let count = 0;
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (EXCLUDED_FOLDERS.some(ex => ex.toLowerCase() === entry.name.toLowerCase())) continue;
      count += await countAllImages(path.join(dir, entry.name));
    } else if (/\.(tif|jpe?g|png)$/i.test(entry.name)) {
      count++;
    }
  }
  return count;
}

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
  crop = true,
  optimizeVideos = false,
  globalStats = null,
  previewMode = false,
  aggressivity = 'standard'
) {
  // =======================
  // INIZIALIZZAZIONE E SCANSIONE CARTELLE
  // =======================
  if (shouldStopFn()) return;

  if (!folderInfo) {
    // Only at the root, count all images for global stats
    const globalImagesTotal = await countAllImages(baseInput);
    const globalImagesProcessed = 0;
    globalStats = {
      globalImagesTotal,
      globalImagesProcessed,
      previewImagesProcessed: 0 // Track preview mode count
    };
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
      currentFile: '',
      globalImagesTotal: globalStats.globalImagesTotal,
      globalImagesProcessed: globalStats.globalImagesProcessed
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
  // In preview mode, stop recursion if we've already processed 4 images
  const shouldRecurse = previewMode
    ? (globalStats && globalStats.previewImagesProcessed < 4)
    : true;

  if (shouldRecurse) {
    for (const sub of dirs) {
      if (
        shouldStopFn() ||
        EXCLUDED_FOLDERS.some(ex => ex.toLowerCase() === sub.toLowerCase())
      ) continue;

      // In preview mode, stop early if we've hit the limit
      if (previewMode && globalStats && globalStats.previewImagesProcessed >= 4) {
        break;
      }

      await processDir(
        path.join(dir, sub),
        progressCallback,
        baseInput,
        baseOutput,
        folderInfo,
        shouldStopFn,
        errorFiles,
        false,
        crop,
        optimizeVideos,
        globalStats,
        previewMode,
        aggressivity
      );
    }
  }

  // =======================
  // PROCESSING IMMAGINI NELLA CARTELLA CORRENTE
  // =======================
  logger.info(`Processing images in: ${dir} (preview: ${previewMode}, aggressivity: ${aggressivity})`);

  // Get thumbnail aliases with aggressivity applied
  const THUMBNAIL_ALIASES = getThumbnailAliases(aggressivity);

  if (images.length) {
    // In preview mode, limit to 4 images total across all folders
    let imagesToProcess = images;
    if (previewMode && globalStats) {
      const remaining = 4 - globalStats.previewImagesProcessed;
      imagesToProcess = images.slice(0, Math.max(0, remaining));
    }

    logger.info(`Found ${images.length} images in: ${dir}, processing ${imagesToProcess.length}`);

    // Skip if no images to process
    if (imagesToProcess.length === 0) {
      return;
    }

    let current = 0;

    // Aggiorna il totale per questa cartella
    if (currentFolderStatus) {
      currentFolderStatus.total = imagesToProcess.length;
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

    const tasks = imagesToProcess.map(file => async () => {
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
          // Convert to WebP with aggressivity-based auto-calculation
          await convertWorker(src, dest, aggressivity);

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

      // Generate thumbnails and track the low_quality one for preview
      let previewThumbnailPath = null;
      for (const alias of Object.keys(THUMBNAIL_ALIASES)) {
        const thumbPath = path.join(thumbsBase, `${path.basename(dest, '.webp')}_${alias}.webp`);
        try {
          await createThumbnailWorker(dest, thumbPath, JSON.stringify(THUMBNAIL_ALIASES[alias]));
          // Store low_quality thumbnail path for live preview
          if (alias === 'low_quality') {
            previewThumbnailPath = thumbPath;
          }
        } catch (e) {
          errorFiles.push(`${dest} (${alias}) - ${e.message}`);
        }
      }

      current++;
      // Update global processed count
      if (globalStats) {
        globalStats.globalImagesProcessed++;
        // Track preview mode separately
        if (previewMode) {
          globalStats.previewImagesProcessed++;
        }
      }

      // Aggiorna progress della cartella corrente
      if (currentFolderStatus) {
        currentFolderStatus.current = current;
        currentFolderStatus.progress = Math.floor((current / imagesToProcess.length) * 100);
      }

      progressCallback({
        type: folderInfo.hasSubfolders ? 'file_progress' : 'main_folder_progress',
        foldersStatus: folderInfo.foldersStatus,
        hasSubfolders: folderInfo.hasSubfolders,
        current,
        total: imagesToProcess.length,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file,
        currentThumbnail: previewThumbnailPath, // Add thumbnail path for live preview
        globalImagesTotal: globalStats ? globalStats.globalImagesTotal : undefined,
        globalImagesProcessed: globalStats ? globalStats.globalImagesProcessed : undefined
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
  // Skip XML copying in preview mode
  if (!previewMode) {
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
  }

  // =======================
  // PROCESSING VIDEO (SE PRESENTI)
  // =======================
  // Skip video processing in preview mode
  if (videos.length && !previewMode) {
    logger.info(`Found ${videos.length} videos in: ${dir}`);

    // Segnale di attesa per processamento video
    progressCallback({
      type: 'video_processing',
      message: 'Attendere, processamento video in corso...',
      currentFolder: path.basename(dir),
      videosCount: videos.length,
      foldersStatus: folderInfo ? folderInfo.foldersStatus : undefined,
      globalImagesTotal: globalStats ? globalStats.globalImagesTotal : undefined,
      globalImagesProcessed: globalStats ? globalStats.globalImagesProcessed : undefined
    });

    if (optimizeVideos) {
      // Verifica se FFmpeg è disponibile
      const ffmpegAvailable = await checkFFmpegAvailable();
      if (!ffmpegAvailable) {
        const errorMsg = 'FFmpeg non è installato nel sistema. Per l\'ottimizzazione video è necessario installare FFmpeg. Visita https://ffmpeg.org/download.html per le istruzioni di installazione.';
        logger.error(`[media_processor] ${errorMsg}`);
        throw new Error(errorMsg);
      }
    }

    if (optimizeVideos) {
      // Ottimizzazione video con worker paralleli
      const videoTasks = videos.map(file => async () => {
        if (shouldStopFn()) return;

        const src = path.join(dir, file);
        const baseName = path.basename(file, path.extname(file));
        const optimizedDest = path.join(outDir, `${baseName}.mp4`);

        try {
          // Ottimizza video per il web
          await optimizeVideo(src, optimizedDest, VIDEO_OPTIMIZATION_PROFILES.web);
          logger.info(`Optimized video: ${file} → ${baseName}.mp4`);

          // Genera thumbnails WebP del video nella cartella thumbnails
          const thumbsVideoDir = path.join(baseOutput, 'thumbnails', relativePath);
          await fs.mkdir(thumbsVideoDir, { recursive: true });

          await generateVideoThumbnails(src, thumbsVideoDir, baseName, {
            timeOffset: VIDEO_THUMBNAIL_PROFILES.preview.timeOffset,
            thumbnailProfiles: {
              low_quality: {
                width: THUMBNAIL_ALIASES.low_quality.size[0],
                height: THUMBNAIL_ALIASES.low_quality.size[1],
                quality: THUMBNAIL_ALIASES.low_quality.quality
              },
              gallery: {
                width: THUMBNAIL_ALIASES.gallery.size[0],
                height: THUMBNAIL_ALIASES.gallery.size[1],
                quality: THUMBNAIL_ALIASES.gallery.quality
              }
            }
          });
          logger.info(`Generated video thumbnails: ${baseName}_*.webp`);

          // Copia anche l'originale se richiesto
          const originalDest = path.join(outDir, file);
          await fs.copyFile(src, originalDest);
          logger.info(`Copied original video: ${file}`);

        } catch (e) {
          logger.error(`Video processing failed for ${file}: ${e.message}`);
          errorFiles.push(`${src} - Video optimization failed: ${e.message}`);

          // Fallback: copia solo l'originale
          try {
            const fallbackDest = path.join(outDir, file);
            await fs.copyFile(src, fallbackDest);
            logger.info(`Fallback copy: ${file}`);
          } catch (copyError) {
            errorFiles.push(`${src} - Copy fallback failed: ${copyError.message}`);
          }
        }
      });

      await processInBatches(videoTasks, Math.min(MAX_PARALLEL, 2)); // Limita video processing
    } else {
      // Copia semplice dei video
      for (const file of videos) {
        if (shouldStopFn()) break;
        const src = path.join(dir, file);
        const dest = path.join(outDir, file);
        try {
          await fs.copyFile(src, dest);
          logger.info(`Copied video: ${file}`);
        } catch (e) {
          errorFiles.push(`${src} - ${e.message}`);
        }
      }
    }

    // Segnale: fine processamento video
    progressCallback({
      type: 'video_processing_done',
      currentFolder: path.basename(dir),
      foldersStatus: folderInfo ? folderInfo.foldersStatus : undefined,
      globalImagesTotal: globalStats ? globalStats.globalImagesTotal : undefined,
      globalImagesProcessed: globalStats ? globalStats.globalImagesProcessed : undefined
    });
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
