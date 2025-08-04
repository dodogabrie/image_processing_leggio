
// File: src/main.js
import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import fs from 'fs/promises';
import path, { dirname } from 'path';
import { fileURLToPath } from 'url';
import * as fsSync from 'fs';

import { processDir } from '../backend/image_processor.js';
import Logger from '../backend/Logger.js';
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

// Handler per file pubblici e dialog
ipcMain.handle('public:readFile', async (_e, filename) => {
  try {
    const publicPath = path.join(process.cwd(), 'public', filename);
    return await fs.readFile(publicPath, 'utf-8');
  } catch (err) {
    logger.error('[main] public:readFile error:', err.message);
    return null;
  }
});

ipcMain.handle('public:writeFile', async (_e, filename, content) => {
  try {
    const publicPath = path.join(process.cwd(), 'public', filename);
    await fs.writeFile(publicPath, content, 'utf-8');
    return { success: true };
  } catch (err) {
    logger.error('[main] public:writeFile error:', err.message);
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
    return files.some(f => f.toLowerCase().endsWith('.csv'));
  } catch (err) {
    logger.warn('[main] hasCsvInFolder error:', err.message);
    return false;
  }
});

/**
 * Handler principale per l'elaborazione delle immagini, CSV e ZIP.
 */
ipcMain.handle('process:images', async (event, dir, outputDir = null, maxCsvLine = null, crop = false, csvMapping = null) => {
  const webContents = event.sender;
  shouldStop = false;

  try {
    // 1) Setup Python if needed
    if (crop) {
      try {
        setupPythonEnv();
      } catch (err) {
        dialog.showErrorBox('Errore ambiente Python', err.message);
        return { success: false, error: err.message };
      }
    }

    // 2) Definizione percorso output
    const baseName = path.basename(dir);
    const finalOutput = outputDir
      ? path.join(outputDir, baseName)
      : path.join(process.env.HOME || process.env.USERPROFILE, 'output1', baseName);

    // 3) Processa immagini
    logger.info(`[main] Processing images in: ${dir}`);
    await processDir(
      dir,
      progress => webContents.send('progress:update', progress),
      undefined,
      finalOutput,
      undefined,
      () => shouldStop,
      undefined,
      true,
      crop
    );
    logger.info(`[main] Images processed successfully in: ${dir}`);
    if (shouldStop) return { success: false, error: "Interrotto dall'utente" };

    // 4) Post-processing CSV e ZIP
    logger.info('[main] Avvio post-processing CSV e ZIP');
    try {
      await postProcessResults(dir, finalOutput, maxCsvLine, csvMapping, webContents);
    } catch (err) {
      logger.error('[main] postProcessResults error:', err.message);
      return { success: false, error: err.message };
    }

    return { success: true };
  } catch (err) {
    logger.error('[main] process:images error:', err.message);
    return { success: false, error: err.message || String(err) };
  }
});

// Stop processing
ipcMain.on('process:stop', () => { shouldStop = true; });

app.whenReady().then(createWindow);

// Gestione eccezioni globali
process.on('uncaughtException', err => logger.error('[main] Uncaught Exception:', err));
process.on('unhandledRejection', reason => logger.error('[main] Unhandled Rejection:', reason));
