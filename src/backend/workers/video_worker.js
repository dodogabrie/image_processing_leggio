// File: backend/workers/video_worker.js
import { spawn } from 'child_process';
import fs from 'fs/promises';
import path from 'path';
import Logger from '../Logger.js';
import { getFFmpegPath } from '../utils/ffmpeg-resolver.js';

const logger = new Logger();

/**
 * Trova il comando FFmpeg (usa binario bundled o installato)
 */
function getFFmpegCommand() {
  return getFFmpegPath();
}

/**
 * Ottimizza un video usando FFmpeg di sistema
 * @param {string} inputPath - Percorso video di input
 * @param {string} outputPath - Percorso video di output
 * @param {Object} options - Opzioni di ottimizzazione
 */
export async function optimizeVideo(inputPath, outputPath, options = {}) {
  const {
    codec = 'libx264',
    crf = 23,
    preset = 'medium',
    maxWidth = 1920,
    maxHeight = 1080,
    audioBitrate = '128k',
    audioCodec = 'aac',
    videoBitrate = null,
    faststart = true,
    extraArgs = [],
    scale = true
  } = options;

  return new Promise((resolve, reject) => {
    const args = [
      '-i', inputPath,
      '-c:v', codec,
      '-crf', crf.toString(),
      ...(preset ? ['-preset', preset] : []),
      ...(scale ? ['-vf', `scale='min(${maxWidth},iw)':'min(${maxHeight},ih)':force_original_aspect_ratio=decrease`] : []),
      ...(videoBitrate ? ['-b:v', videoBitrate] : []),
      '-c:a', audioCodec,
      '-b:a', audioBitrate,
      ...extraArgs,
      ...(faststart ? ['-movflags', '+faststart'] : []),
      '-y', // Sovrascrivi file esistente
      outputPath
    ];

    logger.info(`[video_worker] Starting video optimization: ${path.basename(inputPath)}`);
    logger.info(`[video_worker] FFmpeg command: ffmpeg ${args.join(' ')}`);

    const ffmpegCommand = getFFmpegCommand();
    const ffmpeg = spawn(ffmpegCommand, args);
    let stderr = '';

    ffmpeg.stderr.on('data', (data) => {
      stderr += data.toString();
      // Estrai info di progresso se disponibile
      const progressMatch = stderr.match(/time=(\d+:\d+:\d+\.\d+)/);
      if (progressMatch) {
        logger.info(`[video_worker] Progress: ${progressMatch[1]}`);
      }
    });

    ffmpeg.on('close', async (code) => {
      if (code === 0) {
        try {
          const stats = await fs.stat(outputPath);
          if (stats.size > 0) {
            logger.info(`[video_worker] Video optimization completed: ${path.basename(outputPath)} (${Math.round(stats.size / 1024 / 1024)}MB)`);
            resolve();
          } else {
            throw new Error('Output file is empty');
          }
        } catch (error) {
          reject(new Error(`Output validation failed: ${error.message}`));
        }
      } else {
        logger.error(`[video_worker] FFmpeg failed with code ${code}`);
        logger.error(`[video_worker] FFmpeg stderr: ${stderr}`);
        reject(new Error(`FFmpeg process failed with code ${code}`));
      }
    });

    ffmpeg.on('error', (error) => {
      logger.error(`[video_worker] FFmpeg spawn error: ${error.message}`);
      reject(error);
    });
  });
}

/**
 * Crea una preview video corta (es. 5s) per modalità anteprima
 * @param {string} inputPath - Percorso video di input
 * @param {string} outputPath - Percorso video di output
 * @param {Object} options - Opzioni per la preview
 */
export async function createVideoPreview(inputPath, outputPath, options = {}) {
  const {
    codec = 'libx264',
    crf = 30,
    preset = 'ultrafast',
    maxWidth = 1280,
    maxHeight = 720,
    audioBitrate = '96k',
    audioCodec = 'aac',
    durationSeconds = 5
  } = options;

  return new Promise((resolve, reject) => {
    const args = [
      '-i', inputPath,
      '-t', durationSeconds.toString(),
      '-c:v', codec,
      '-crf', crf.toString(),
      ...(preset ? ['-preset', preset] : []),
      '-vf', `scale='min(${maxWidth},iw)':'min(${maxHeight},ih)':force_original_aspect_ratio=decrease`,
      '-c:a', audioCodec,
      '-b:a', audioBitrate,
      '-movflags', '+faststart',
      '-y',
      outputPath
    ];

    logger.info(`[video_worker] Starting video preview: ${path.basename(inputPath)}`);
    logger.info(`[video_worker] FFmpeg preview command: ffmpeg ${args.join(' ')}`);

    const ffmpegCommand = getFFmpegCommand();
    const ffmpeg = spawn(ffmpegCommand, args);
    let stderr = '';

    ffmpeg.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    ffmpeg.on('close', async (code) => {
      if (code === 0) {
        try {
          const stats = await fs.stat(outputPath);
          if (stats.size > 0) {
            logger.info(`[video_worker] Video preview created: ${path.basename(outputPath)} (${Math.round(stats.size / 1024 / 1024)}MB)`);
            resolve();
          } else {
            throw new Error('Output file is empty');
          }
        } catch (error) {
          reject(new Error(`Preview output validation failed: ${error.message}`));
        }
      } else {
        logger.error(`[video_worker] FFmpeg preview failed with code ${code}`);
        logger.error(`[video_worker] FFmpeg preview stderr: ${stderr}`);
        reject(new Error(`FFmpeg preview failed with code ${code}`));
      }
    });

    ffmpeg.on('error', (error) => {
      logger.error(`[video_worker] FFmpeg preview spawn error: ${error.message}`);
      reject(error);
    });
  });
}

/**
 * Genera thumbnails WebP da un video estraendo prima un frame
 * @param {string} inputPath - Percorso video di input
 * @param {string} outputDir - Directory dove salvare le thumbnails
 * @param {string} baseName - Nome base per i file thumbnail
 * @param {Object} options - Opzioni per le thumbnails
 */
export async function generateVideoThumbnails(inputPath, outputDir, baseName, options = {}) {
  const {
    timeOffset = '00:00:01',
    thumbnailProfiles = {
      low_quality: { width: 640, height: 480, quality: 75 },
      gallery: { width: 1920, height: 1080, quality: 85 }
    }
  } = options;

  // Prima estrai un frame temporaneo in alta qualità
  const tempFramePath = path.join(outputDir, `${baseName}_temp_frame.jpg`);
  
  // Estrai frame dal video
  await extractVideoFrame(inputPath, tempFramePath, timeOffset);
  
  try {
    // Ora crea le thumbnails WebP usando il sistema esistente
    const { createThumbnailWorker } = await import('../worker_forks.js');
    
    for (const [alias, profile] of Object.entries(thumbnailProfiles)) {
      const thumbPath = path.join(outputDir, `${baseName}_${alias}.webp`);
      const thumbOptions = {
        size: [profile.width, profile.height],
        quality: profile.quality,
        crop: false,
        format: 'webp'
      };
      
      try {
        await createThumbnailWorker(tempFramePath, thumbPath, JSON.stringify(thumbOptions));
        logger.info(`[video_worker] Created thumbnail: ${baseName}_${alias}.webp`);
      } catch (error) {
        logger.warn(`[video_worker] Failed to create ${alias} thumbnail: ${error.message}`);
      }
    }
    
    // Pulisci il frame temporaneo
    await fs.unlink(tempFramePath);
    logger.info(`[video_worker] Thumbnails generation completed for: ${baseName}`);
  } catch (error) {
    // Cleanup in caso di errore
    try {
      await fs.unlink(tempFramePath);
    } catch {}
    throw error;
  }
}

/**
 * Estrae un singolo frame da un video
 * @param {string} inputPath - Percorso video di input
 * @param {string} outputPath - Percorso frame di output
 * @param {string} timeOffset - Offset temporale (es: '00:00:01')
 */
export async function extractVideoFrame(inputPath, outputPath, timeOffset = '00:00:01') {
  return new Promise((resolve, reject) => {
    const args = [
      '-i', inputPath,
      '-ss', timeOffset,
      '-vframes', '1',
      '-q:v', '2', // Alta qualità
      '-y',
      outputPath
    ];

    logger.info(`[video_worker] Extracting frame from: ${path.basename(inputPath)} at ${timeOffset}`);

    const ffmpegCommand = getFFmpegCommand();
    const ffmpeg = spawn(ffmpegCommand, args);
    let stderr = '';

    ffmpeg.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    ffmpeg.on('close', async (code) => {
      if (code === 0) {
        try {
          const stats = await fs.stat(outputPath);
          if (stats.size > 0) {
            logger.info(`[video_worker] Frame extracted: ${path.basename(outputPath)}`);
            resolve();
          } else {
            throw new Error('Frame file is empty');
          }
        } catch (error) {
          reject(new Error(`Frame validation failed: ${error.message}`));
        }
      } else {
        logger.error(`[video_worker] Frame extraction failed with code ${code}: ${stderr}`);
        reject(new Error(`Frame extraction failed with code ${code}`));
      }
    });

    ffmpeg.on('error', (error) => {
      logger.error(`[video_worker] FFmpeg frame extraction error: ${error.message}`);
      reject(error);
    });
  });
}

/**
 * Controlla se FFmpeg è disponibile nel sistema
 */
export async function checkFFmpegAvailable() {
  return new Promise((resolve) => {
    const ffmpegCommand = getFFmpegCommand();
    const ffmpeg = spawn(ffmpegCommand, ['-version']);
    
    ffmpeg.on('close', (code) => {
      if (code === 0) {
        logger.info(`[video_worker] FFmpeg available: ${ffmpegCommand}`);
        resolve(true);
      } else {
        logger.warn(`[video_worker] FFmpeg not available (code ${code})`);
        resolve(false);
      }
    });
    
    ffmpeg.on('error', (error) => {
      logger.warn(`[video_worker] FFmpeg check failed: ${error.message}`);
      resolve(false);
    });
  });
}
