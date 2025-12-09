// File: backend/utils/ffmpeg-resolver.js
import path from 'path';
import { fileURLToPath } from 'url';
import ffmpegInstaller from '@ffmpeg-installer/ffmpeg';
import Logger from '../Logger.js';

const logger = new Logger();
const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Check if we're running in a packaged Electron app
 * Safe to call from worker processes
 */
function isPackaged() {
  // Check if NODE_ENV is development (set in package.json scripts)
  if (process.env.NODE_ENV === 'development') {
    return false;
  }

  // Check if we're running from the asar archive (production)
  // In packaged mode, __dirname will contain '.asar'
  if (__dirname.includes('.asar')) {
    return true;
  }

  // Additional check: in packaged mode, resourcesPath won't include 'node_modules/electron'
  if (process.resourcesPath && !process.resourcesPath.includes('node_modules/electron')) {
    return true;
  }

  return false;
}

/**
 * Resolves the FFmpeg binary path for both development and packaged modes
 * @returns {string} Path to the FFmpeg executable
 */
export function getFFmpegPath() {
  // In development, use the installed package binary
  if (!isPackaged()) {
    logger.info(`[ffmpeg-resolver] Using FFmpeg from npm package: ${ffmpegInstaller.path}`);
    return ffmpegInstaller.path;
  }

  // In production, use the binary bundled in resources
  // The electron-builder extraResources config will copy it to resources/
  const platform = process.platform;
  let binaryName;

  if (platform === 'win32') {
    binaryName = 'ffmpeg.exe';
  } else if (platform === 'darwin') {
    binaryName = 'ffmpeg';
  } else {
    // Linux
    binaryName = 'ffmpeg';
  }

  const ffmpegPath = path.join(process.resourcesPath, 'ffmpeg', platform, binaryName);
  logger.info(`[ffmpeg-resolver] Using bundled FFmpeg: ${ffmpegPath}`);

  return ffmpegPath;
}

/**
 * Get FFprobe path (useful for video metadata extraction)
 * @returns {string} Path to the FFprobe executable
 */
export function getFFprobePath() {
  if (!isPackaged()) {
    // FFmpeg installer package also includes ffprobe path if available
    const ffprobePath = ffmpegInstaller.path.replace('ffmpeg', 'ffprobe');
    logger.info(`[ffmpeg-resolver] Using FFprobe from npm package: ${ffprobePath}`);
    return ffprobePath;
  }

  const platform = process.platform;
  let binaryName;

  if (platform === 'win32') {
    binaryName = 'ffprobe.exe';
  } else {
    binaryName = 'ffprobe';
  }

  const ffprobePath = path.join(process.resourcesPath, 'ffmpeg', platform, binaryName);
  logger.info(`[ffmpeg-resolver] Using bundled FFprobe: ${ffprobePath}`);

  return ffprobePath;
}
