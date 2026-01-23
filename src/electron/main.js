
// File: src/main.js
import { app, BrowserWindow, ipcMain, dialog, shell, protocol, net } from 'electron';
import fs from 'fs/promises';
import path, { dirname } from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import * as fsSync from 'fs';

import { processDir } from '../backend/media_processor.js';
import Logger, { setLogDirectory, getLogFilePath } from '../backend/Logger.js';
import { getCsvHeaders, getCsvPreview } from '../backend/workers/organize_by_csv.js';
import { setupPythonEnv } from '../backend/scripts/setup-python.js';
import { postProcessResults } from '../backend/postprocessing.js';

// Shim per __dirname in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const logger = new Logger();
let shouldStop = false;

/**
 * Crea la finestra principale dell'app Electron.
 */
function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  logger.info('[main] Creating main window');

  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:3000');
  } else {
    // In produzione, il file è nella stessa cartella dell'app pacchettata
    const htmlPath = app.isPackaged 
      ? path.join(process.resourcesPath, 'app.asar', 'dist', 'client', 'index.html')
      : path.join(__dirname, '../../dist/client/index.html');
    win.loadFile(htmlPath);
  }
}

// Lettura file pubblico
ipcMain.handle('public:readFile', async (_e, filename) => {
  try {
    const publicPath = app.isPackaged
      ? path.join(process.resourcesPath, 'public', filename)
      : path.join(process.cwd(), 'public', filename);
    return await fs.readFile(publicPath, 'utf-8');
  } catch (err) {
    logger.error('[main] public:readFile error:', err.message);
    return null;
  }
});

// Scrittura file pubblico
ipcMain.handle('public:writeFile', async (_e, filename, content) => {
  try {
    const publicPath = app.isPackaged
      ? path.join(process.resourcesPath, 'public', filename)
      : path.join(process.cwd(), 'public', filename);
    await fs.writeFile(publicPath, content, 'utf-8');
    return { success: true };
  } catch (err) {
    logger.error('[main] public:writeFile error:', err.message);
    return { success: false, error: err.message };
  }
});

// Eliminazione file pubblico
ipcMain.handle('public:deleteFile', async (_e, filename) => {
  try {
    const publicPath = app.isPackaged
      ? path.join(process.resourcesPath, 'public', filename)
      : path.join(process.cwd(), 'public', filename);
    await fs.unlink(publicPath);
    return { success: true };
  } catch (err) {
    logger.error('[main] public:deleteFile error:', err.message);
    return { success: false, error: err.message };
  }
});

// Handler fs e dialog
ipcMain.handle('fs:readDir', async (_e, dir) => {
  try {
    return await fs.readdir(dir);
  } catch (err) {
    logger.warn('[main] fs:readDir fail:', dir, err.message);
    return [];
  }
});

// Handler per leggere thumbnail come base64 data URL
ipcMain.handle('fs:readThumbnailAsDataUrl', async (_e, filePath) => {
  try {
    const buffer = await fs.readFile(filePath);
    const base64 = buffer.toString('base64');
    const ext = path.extname(filePath).toLowerCase();
    let mimeType = 'image/webp'; // Default

    if (ext === '.jpg' || ext === '.jpeg') mimeType = 'image/jpeg';
    else if (ext === '.png') mimeType = 'image/png';

    return `data:${mimeType};base64,${base64}`;
  } catch (err) {
    logger.warn('[main] fs:readThumbnailAsDataUrl fail:', filePath, err.message);
    return null;
  }
});

// Handler per leggere un'immagine completa come data URL (per la modal)
ipcMain.handle('fs:readImageAsDataUrl', async (_e, filePath) => {
  try {
    const buffer = await fs.readFile(filePath);
    const base64 = buffer.toString('base64');
    const ext = path.extname(filePath).toLowerCase();
    let mimeType = 'image/webp';

    if (ext === '.jpg' || ext === '.jpeg') mimeType = 'image/jpeg';
    else if (ext === '.png') mimeType = 'image/png';
    else if (ext === '.tif' || ext === '.tiff') mimeType = 'image/tiff';

    return `data:${mimeType};base64,${base64}`;
  } catch (err) {
    logger.warn('[main] fs:readImageAsDataUrl fail:', filePath, err.message);
    return null;
  }
});

// Handler per leggere un file JSON arbitrario se esiste
ipcMain.handle('fs:readJsonFile', async (_e, filePath) => {
  try {
    if (!fsSync.existsSync(filePath)) return null;
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (err) {
    logger.warn('[main] fs:readJsonFile fail:', filePath, err.message);
    return null;
  }
});

// Handler per listare directory con metadati e thumbnail associati
ipcMain.handle('fs:listEntriesDetailed', async (_e, dir, organizedRoot = null, thumbnailsRoot = null) => {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    const relDir = organizedRoot ? path.relative(organizedRoot, dir) : '';
    const thumbsDir = thumbnailsRoot && relDir !== undefined ? path.join(thumbnailsRoot, relDir) : null;

    const detailed = [];
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const isDirectory = entry.isDirectory();
      const ext = path.extname(entry.name).toLowerCase();
      const isImage = ['.webp', '.jpg', '.jpeg', '.png', '.tif', '.tiff'].includes(ext);

      let thumbnailPath = null;
      if (!isDirectory && isImage && thumbsDir) {
        const baseName = path.basename(entry.name, ext);
        const lowQuality = path.join(thumbsDir, `${baseName}_low_quality.webp`);
        const gallery = path.join(thumbsDir, `${baseName}_gallery.webp`);

        if (fsSync.existsSync(lowQuality)) thumbnailPath = lowQuality;
        else if (fsSync.existsSync(gallery)) thumbnailPath = gallery;
        else thumbnailPath = fullPath; // fallback alla stessa immagine
      }

      detailed.push({
        name: entry.name,
        path: fullPath,
        type: isDirectory ? 'directory' : 'file',
        isImage,
        thumbnailPath
      });
    }

    const breadcrumbs = [];
    if (organizedRoot) {
      const rel = path.relative(organizedRoot, dir);
      let accumulated = organizedRoot;

      breadcrumbs.push({
        name: path.basename(organizedRoot) || organizedRoot,
        path: organizedRoot
      });

      if (rel && rel !== '') {
        const parts = rel.split(path.sep).filter(Boolean);
        for (const part of parts) {
          accumulated = path.join(accumulated, part);
          breadcrumbs.push({ name: part, path: accumulated });
        }
      }
    }

    return { entries: detailed, breadcrumbs };
  } catch (err) {
    logger.warn('[main] fs:listEntriesDetailed fail:', dir, err.message);
    return { entries: [], breadcrumbs: [], error: err.message };
  }
});

// Trova un originale corrispondente (best-effort) rispetto a un file elaborato
ipcMain.handle('fs:findOriginalMatch', async (_e, processedPath, originalRoot) => {
  if (!processedPath || !originalRoot) return null;

  const tryExts = ['.tif', '.tiff', '.jpg', '.jpeg', '.png', '.webp'];
  const processedExt = path.extname(processedPath);
  const processedBase = path.basename(processedPath, processedExt);

  // 1) Prova con struttura relativa dopo "organized" se presente
  const parts = processedPath.split(path.sep);
  const organizedIdx = parts.lastIndexOf('organized');
  if (organizedIdx !== -1) {
    const relParts = parts.slice(organizedIdx + 1, parts.length - 1); // cartelle dopo organized
    const relDir = relParts.join(path.sep);
    for (const ext of tryExts) {
      const candidate = path.join(originalRoot, relDir, `${processedBase}${ext}`);
      if (fsSync.existsSync(candidate)) {
        return candidate;
      }
    }
  }

  // 2) Prova usando identifier (ultimo segmento dopo underscore) per strutture diverse
  const identifier = processedBase.includes('_')
    ? processedBase.split('_').pop()
    : processedBase;
  for (const ext of tryExts) {
    const candidate = path.join(originalRoot, `${identifier}${ext}`);
    if (fsSync.existsSync(candidate)) {
      return candidate;
    }
  }

  // 3) Ricerca ricorsiva limitata
  let found = null;
  const stack = [originalRoot];
  let visited = 0;
  const maxVisited = 5000; // evita blocchi su alberi enormi

  while (stack.length && !found && visited < maxVisited) {
    const current = stack.pop();
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (visited >= maxVisited) break;
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
      } else {
        const ext = path.extname(entry.name).toLowerCase();
        if (!tryExts.includes(ext)) continue;
        const base = path.basename(entry.name, ext);
        if (base === processedBase || base === identifier) {
          found = full;
          break;
        }
      }
      visited++;
    }
  }

  if (found) return found;
  return null;
});
ipcMain.handle('dialog:openFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
  return canceled ? null : filePaths[0];
});
ipcMain.handle('dialog:openOutputFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory', 'createDirectory'] });
  return canceled ? null : filePaths[0];
});

// Handler CSV utilità
ipcMain.handle('csv:getHeaders', async (_e, csvPath) => getCsvHeaders(csvPath));
ipcMain.handle('csv:getPreview', async (_e, csvPath, maxRows) => getCsvPreview(csvPath, maxRows));
ipcMain.handle('hasCsvInFolder', async (_e, dir) => {
  try {
    const files = await fs.readdir(dir);
    return files.some(f => {
      const lower = f.toLowerCase();
      return lower.endsWith('.csv') || lower.endsWith('.xlsx');
    });
  } catch (err) {
    logger.warn('[main] hasCsvInFolder error:', err.message);
    return false;
  }
});

/**
 * Handler principale per l'elaborazione delle immagini, CSV e ZIP.
 */
ipcMain.handle('process:images', async (event, dir, outputDir = null, maxCsvLine = null, crop = false, csvMapping = null, optimizeVideos = false, optimizeImages = true, previewMode = false, aggressivity = 'standard') => {
  const webContents = event.sender;
  shouldStop = false;

  try {
    // 1) Setup Python if needed (only if optimizing images with crop)
    if (optimizeImages && crop) {
      try {
        await setupPythonEnv();
        logger.info('[main] Python environment setup completed');
      } catch (err) {
        logger.error('[main] Python setup error:', err.message);
        // In development, continua senza Python virtuale
        if (process.env.NODE_ENV === 'development') {
          logger.warn('[main] Continuing without virtual environment in development mode');
        } else {
          dialog.showErrorBox('Errore ambiente Python', err.message);
          return { success: false, error: err.message };
        }
      }
    }

    // 2) Definizione percorso output
    const baseName = path.basename(dir);
    const finalOutput = outputDir
      ? path.join(outputDir, baseName)
      : path.join(process.env.HOME || process.env.USERPROFILE, 'output1', baseName);

    // 3) Processa immagini e video (only if optimizeImages is true)
    if (optimizeImages) {
      logger.info(`[main] Processing images in: ${dir} (preview: ${previewMode}, aggressivity: ${aggressivity})`);
      await processDir(
        dir,
        progress => webContents.send('progress:update', progress),
        undefined,
        finalOutput,
        undefined,
        () => shouldStop,
        undefined,
        true,
        crop,
        optimizeVideos,
        undefined,
        previewMode,
        aggressivity
      );
      logger.info(`[main] Images processed successfully in: ${dir}`);
      if (shouldStop) return { success: false, error: "Interrotto dall'utente" };
    } else {
      logger.info('[main] Skipping image processing (optimizeImages=false)');
    }

    // 4) In preview mode, collect file sizes and skip CSV processing
    if (previewMode && optimizeImages) {
      logger.info('[main] Preview mode: collecting file sizes');
      const previewFileSizes = [];
      try {
        // Recursively find all WebP files in output directory
        async function findWebpFiles(dir, collected = []) {
          if (collected.length >= 4) return collected;

          const entries = await fs.readdir(dir, { withFileTypes: true });

          for (const entry of entries) {
            if (collected.length >= 4) break;

            const fullPath = path.join(dir, entry.name);

            if (entry.isDirectory()) {
              await findWebpFiles(fullPath, collected);
            } else if (entry.name.endsWith('.webp')) {
              const stats = await fs.stat(fullPath);
              collected.push({
                name: entry.name,
                size: stats.size
              });
            }
          }

          return collected;
        }

        await findWebpFiles(finalOutput, previewFileSizes);

        logger.info(`[main] Preview mode: collected ${previewFileSizes.length} file sizes`);
        return { success: true, previewFileSizes, outputDir: finalOutput };
      } catch (err) {
        logger.error('[main] Preview mode file size collection error:', err.message);
        return { success: false, error: err.message };
      }
    }

    // 5) Post-processing CSV e ZIP (skip in preview mode)
    if (!previewMode) {
      logger.info('[main] Avvio post-processing CSV e ZIP');
      try {
        const webpSourceDir = optimizeImages ? finalOutput : dir;
        await postProcessResults(dir, finalOutput, maxCsvLine, csvMapping, webContents, webpSourceDir);
      } catch (err) {
        logger.error('[main] postProcessResults error:', err.message);
        return { success: false, error: err.message };
      }
    }

    return { 
      success: true,
      outputDir: finalOutput,
      organizedDir: path.join(finalOutput, 'organized'),
      organizedThumbsDir: path.join(finalOutput, 'organized_thumbnails')
    };
  } catch (err) {
    logger.error('[main] process:images error:', err.message);
    return { success: false, error: err.message || String(err) };
  }
});

// Handler per pulire i file di anteprima
ipcMain.handle('cleanup:preview', async (_e, outputDir) => {
  try {
    logger.info(`[main] Cleaning up preview files in: ${outputDir}`);
    await fs.rm(outputDir, { recursive: true, force: true });
    logger.info('[main] Preview cleanup completed');
    return { success: true };
  } catch (err) {
    logger.error('[main] Preview cleanup error:', err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('public:openExternal', async (_e, url) => {
  try {
    await shell.openExternal(url);
    return { success: true };
  } catch (err) {
    logger.error('[main] public:openExternal error:', err.message);
    return { success: false, error: err.message || String(err) };
  }
});

// Stop processing
ipcMain.on('process:stop', () => { shouldStop = true; });

// Log file handlers
ipcMain.handle('log:getContent', async () => {
  try {
    const logPath = getLogFilePath();
    logger.info(`[main] log:getContent requested, path: ${logPath}`);
    if (!logPath || !fsSync.existsSync(logPath)) {
      return { success: false, error: `Log file not found at ${logPath}` };
    }
    const content = await fs.readFile(logPath, 'utf-8');
    return { success: true, content, path: logPath };
  } catch (err) {
    logger.error('[main] log:getContent error:', err.message);
    return { success: false, error: err.message };
  }
});

ipcMain.handle('log:getPath', async () => {
  const logPath = getLogFilePath();
  logger.info(`[main] log:getPath: ${logPath}`);
  return { path: logPath, exists: logPath && fsSync.existsSync(logPath) };
});

ipcMain.handle('log:saveAs', async () => {
  try {
    const logPath = getLogFilePath();
    logger.info(`[main] log:saveAs requested, path: ${logPath}`);
    if (!logPath || !fsSync.existsSync(logPath)) {
      return { success: false, error: `Log file not found at ${logPath}` };
    }

    const { canceled, filePath } = await dialog.showSaveDialog({
      title: 'Save Log File',
      defaultPath: `leggio_log_${new Date().toISOString().slice(0, 10)}.log`,
      filters: [{ name: 'Log Files', extensions: ['log', 'txt'] }]
    });

    if (canceled || !filePath) {
      return { success: false, canceled: true };
    }

    await fs.copyFile(logPath, filePath);
    return { success: true, savedTo: filePath };
  } catch (err) {
    logger.error('[main] log:saveAs error:', err.message);
    return { success: false, error: err.message };
  }
});

// Register custom protocol scheme BEFORE app.whenReady()
protocol.registerSchemesAsPrivileged([
  {
    scheme: 'media-file',
    privileges: {
      secure: true,
      supportFetchAPI: true,
      corsEnabled: false,
      bypassCSP: false
    }
  }
]);

app.whenReady().then(() => {
  // Initialize log directory to userData (writable on all platforms)
  setLogDirectory(app.getPath('userData'));
  logger.info('[main] Application starting, log directory initialized');

  // Register protocol handler for serving media files efficiently
  protocol.handle('media-file', (request) => {
    const url = request.url.slice('media-file://'.length);
    const filePath = decodeURIComponent(url);

    // Security: prevent directory traversal
    const normalizedPath = path.normalize(filePath);
    if (normalizedPath.includes('..')) {
      logger.warn('[main] Rejected media-file request with directory traversal:', filePath);
      return new Response('Forbidden', { status: 403 });
    }

    // Security: ensure file exists and is a file (not directory)
    if (!fsSync.existsSync(normalizedPath) || !fsSync.statSync(normalizedPath).isFile()) {
      logger.warn('[main] media-file not found or not a file:', normalizedPath);
      return new Response('Not Found', { status: 404 });
    }

    // Serve the file using net.fetch with file:// URL
    return net.fetch(pathToFileURL(normalizedPath).toString());
  });

  createWindow();
});

// Gestione eccezioni globali
process.on('uncaughtException', err => logger.error('[main] Uncaught Exception:', err));
process.on('unhandledRejection', reason => logger.error('[main] Unhandled Rejection:', reason));
