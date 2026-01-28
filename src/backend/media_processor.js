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
import { calculateOptimalWorkers, getSystemResources, monitorResources } from './utils/resource-manager.js';

const logger = new Logger();

// Profili delle thumbnails generate (Base - modificato da aggressivity)
const THUMBNAIL_ALIASES_BASE = {
  low_quality:  { size: [640, 480],   quality: 75, crop: false, format: 'webp' },
  gallery:      { size: [1920, 1080], quality: 75, crop: false, format: 'webp' }
};

// Profili di aggressività per qualità immagini
// Formula base: quality = Math.round(baseline - originalKB / divisor)
// Shifted to be more aggressive across all modes
const AGGRESSIVITY_PROFILES = {
  low: {
    formulaBaseline: 90,      // Was "standard" - balanced quality/size
    formulaDivisor: 27.3,
    thumbnailQualityModifier: 0,
    description: 'Bilanciamento qualità/dimensioni'
  },
  standard: {
    formulaBaseline: 80,      // Was "high" - good compression
    formulaDivisor: 22,
    thumbnailQualityModifier: -10,  // Slightly reduced from -15
    description: 'Compressione buona, file ridotti'
  },
  high: {
    formulaBaseline: 70,      // NEW - extreme compression
    formulaDivisor: 18,       // Faster quality decay
    thumbnailQualityModifier: -20, // Heavy thumbnail compression
    description: 'Compressione massima, file molto piccoli'
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
    // Visually lossless-ish MP4 (H.264) for speed + compatibility
    codec: 'libx264',
    crf: 23,
    preset: 'slow',
    maxWidth: 1920,
    maxHeight: 1080,
    audioBitrate: '128k',
    audioCodec: 'aac',
    faststart: true,
    scale: false
  },
  mobile: {
    codec: 'libx264',
    crf: 30,  // Even higher compression for mobile
    preset: 'fast',
    maxWidth: 1280,
    maxHeight: 720,
    audioBitrate: '64k',  // Lower bitrate for mobile
    audioCodec: 'aac'
  },
  archive: {
    codec: 'libx265',
    crf: 30,  // Increased from 28 for better compression
    preset: 'slow',
    maxWidth: 1920,
    maxHeight: 1080,
    audioBitrate: '96k',  // Reduced from 128k
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
  aggressivity = 'standard',
  _depth = 0,
  _visitedPaths = null
) {
  // =======================
  // INIZIALIZZAZIONE E SCANSIONE CARTELLE
  // =======================
  if (shouldStopFn()) return;

  // Protection against circular references and deep recursion
  const MAX_DEPTH = 50;
  const MAX_PATH_LENGTH = 3500; // Leave room for output path generation

  // Initialize visited paths tracking on first call
  if (_visitedPaths === null) {
    _visitedPaths = new Set();
  }

  // Check depth limit
  if (_depth > MAX_DEPTH) {
    logger.error(`[media_processor] Max depth (${MAX_DEPTH}) exceeded at: ${dir}`);
    throw new Error(`Maximum folder depth (${MAX_DEPTH}) exceeded. Possible circular reference or excessively nested folders.`);
  }

  // Check path length
  if (dir.length > MAX_PATH_LENGTH) {
    logger.error(`[media_processor] Path too long (${dir.length} chars): ${dir.substring(0, 150)}...`);
    throw new Error(`Path too long (${dir.length} characters). Maximum allowed is ${MAX_PATH_LENGTH}.`);
  }

  // Check for circular references
  const realPath = path.resolve(dir);
  if (_visitedPaths.has(realPath)) {
    logger.warn(`[media_processor] Circular reference detected, skipping: ${dir}`);
    return; // Skip this directory
  }
  _visitedPaths.add(realPath);

  if (!folderInfo) {
    // Log system resources at the start of processing
    const systemResources = getSystemResources();
    logger.info(`[media_processor] === System Resources ===`);
    logger.info(`[media_processor] CPU: ${systemResources.cpuCount} cores (${systemResources.cpuModel})`);
    logger.info(`[media_processor] RAM: ${systemResources.usedMemoryGB}GB / ${systemResources.totalMemoryGB}GB used (${systemResources.memoryUsagePercent}%)`);
    logger.info(`[media_processor] Free RAM: ${systemResources.freeMemoryGB}GB`);
    logger.info(`[media_processor] Platform: ${systemResources.platform} ${systemResources.arch}`);
    logger.info(`[media_processor] ========================`);

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

  // Calculate average file size for resource optimization
  let avgImageSizeMB = 0;
  if (images.length > 0) {
    try {
      const sampleSize = Math.min(5, images.length); // Sample first 5 images
      let totalSize = 0;
      for (let i = 0; i < sampleSize; i++) {
        const stats = await fs.stat(path.join(dir, images[i]));
        totalSize += stats.size;
      }
      avgImageSizeMB = (totalSize / sampleSize) / (1024 * 1024);
    } catch (e) {
      logger.warn(`[media_processor] Could not calculate avg image size: ${e.message}`);
    }
  }

  let avgVideoSizeMB = 0;
  if (videos.length > 0) {
    try {
      const sampleSize = Math.min(3, videos.length); // Sample first 3 videos
      let totalSize = 0;
      for (let i = 0; i < sampleSize; i++) {
        const stats = await fs.stat(path.join(dir, videos[i]));
        totalSize += stats.size;
      }
      avgVideoSizeMB = (totalSize / sampleSize) / (1024 * 1024);
    } catch (e) {
      logger.warn(`[media_processor] Could not calculate avg video size: ${e.message}`);
    }
  }

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
        aggressivity,
        _depth + 1,
        _visitedPaths
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

    // Only process images if there are any to process
    if (imagesToProcess.length > 0) {
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

        // Skip if thumbnail already exists
        let thumbExists = false;
        try {
          if ((await fs.stat(thumbPath)).size > 0) thumbExists = true;
        } catch {}

        if (!thumbExists) {
          try {
            await createThumbnailWorker(dest, thumbPath, JSON.stringify(THUMBNAIL_ALIASES[alias]));
          } catch (e) {
            errorFiles.push(`${dest} (${alias}) - ${e.message}`);
          }
        }

        // Store low_quality thumbnail path for live preview (whether new or existing)
        if (alias === 'low_quality') {
          previewThumbnailPath = thumbPath;
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

      // Calculate optimal workers for image processing
      const imageWorkers = calculateOptimalWorkers({
        taskType: 'image',
        avgFileSizeMB: avgImageSizeMB,
        minWorkers: 1,
        maxWorkers: null
      });

      logger.info(`[media_processor] Using ${imageWorkers} workers for image processing (avg size: ${avgImageSizeMB.toFixed(1)}MB)`);
      await processInBatches(tasks, imageWorkers);

      // Segna cartella come completata
      if (currentFolderStatus) {
        currentFolderStatus.status = 'completed';
        currentFolderStatus.progress = 100;
      }
    } // End of imagesToProcess.length > 0 check
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
        const errorMsg = 'FFmpeg non è disponibile. L\'applicazione include FFmpeg integrato, ma non è stato possibile avviarlo. Prova a reinstallare l\'applicazione.';
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
        const originalDest = path.join(outDir, file);

        // Skip if optimized or original video already exists
        let optimizedExists = false;
        let originalExists = false;
        let optimizedSize = 0;
        let originalSize = 0;
        try {
          const stats = await fs.stat(optimizedDest);
          if (stats.size > 0) {
            optimizedExists = true;
            optimizedSize = stats.size;
          }
        } catch {}
        try {
          const stats = await fs.stat(originalDest);
          if (stats.size > 0) {
            originalExists = true;
            originalSize = stats.size;
          }
        } catch {}

        try {
          if (originalExists) {
            if (optimizedExists && optimizedSize > originalSize) {
              try {
                await fs.unlink(optimizedDest);
                logger.info(`Removed larger optimized video: ${baseName}.mp4 (kept original)`);
              } catch {}
            }
            logger.info(`Skipped video optimization (kept original): ${file}`);
          } else if (optimizedExists) {
            logger.info(`Skipped video (already exists): ${file}`);
          } else {
            const srcStats = await fs.stat(src);
            // Ottimizza video per il web
            await optimizeVideo(src, optimizedDest, {
              ...VIDEO_OPTIMIZATION_PROFILES.web,
              onProgress: ({ time, total, percent }) => {
                progressCallback({
                  type: 'video_processing',
                  message: (typeof percent === 'number')
                    ? `Video ${file}: ${percent}%`
                    : (total ? `Video ${file}: ${time} / ${total}` : `Video ${file}: ${time}`),
                  currentFolder: path.basename(dir),
                  currentFile: file,
                  foldersStatus: folderInfo ? folderInfo.foldersStatus : undefined,
                  globalImagesTotal: globalStats ? globalStats.globalImagesTotal : undefined,
                  globalImagesProcessed: globalStats ? globalStats.globalImagesProcessed : undefined
                });
              }
            });
            const outStats = await fs.stat(optimizedDest);
            if (outStats.size > srcStats.size) {
              await fs.unlink(optimizedDest);
              await fs.copyFile(src, originalDest);
              logger.info(`Optimized video larger than original, kept original: ${file}`);
              originalExists = true;
              originalSize = srcStats.size;
            } else {
            logger.info(`Optimized video: ${file} → ${baseName}.mp4`);
            }
          }
          

          // Genera thumbnails WebP del video nella cartella thumbnails
          const thumbsVideoDir = path.join(baseOutput, 'thumbnails', relativePath);
          await fs.mkdir(thumbsVideoDir, { recursive: true });

          // Check if video thumbnails already exist
          const lowQualityThumb = path.join(thumbsVideoDir, `${baseName}_low_quality.webp`);
          let videoThumbsExist = false;
          try {
            if ((await fs.stat(lowQualityThumb)).size > 0) videoThumbsExist = true;
          } catch {}

          if (!videoThumbsExist) {
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
          } else {
            logger.info(`Skipped video thumbnails (already exist): ${baseName}`);
          }

          // Don't copy the original - we only keep the optimized MP4

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

      // Calculate optimal workers for video processing
      const videoWorkers = calculateOptimalWorkers({
        taskType: 'video',
        avgFileSizeMB: avgVideoSizeMB,
        minWorkers: 1,
        maxWorkers: 3 // Videos are very resource-intensive, cap at 3
      });

      logger.info(`[media_processor] Using ${videoWorkers} workers for video processing (avg size: ${avgVideoSizeMB.toFixed(1)}MB)`);
      await processInBatches(videoTasks, videoWorkers);
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
