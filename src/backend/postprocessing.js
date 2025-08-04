// File: backend/postprocessing.js
import fs from 'fs/promises';
import path, { dirname } from 'path';
import { fileURLToPath } from 'url';
import { fork } from 'child_process';

import * as fsSync from 'fs';
import Logger from './Logger.js';
import { organizeFromCsv } from './workers/organize_by_csv.js';

// Shim per __dirname in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);const logger = new Logger();

/**
 * Esegue post-processing: ordinamento da CSV (se presente) e creazione ZIP.
 * @param {string} dir - Directory di input (contenente eventuale CSV).
 * @param {string} finalOutput - Directory di output per organizzati e ZIP.
 * @param {number|null} maxCsvLine - Numero massimo di righe CSV da processare.
 * @param {Object|null} csvMapping - Mappatura colonne CSV.
 * @param {Electron.WebContents} webContents - Canale per invio progress log.
 * @throws Error in caso di fallimento.
 */
export async function postProcessResults(
  dir,
  finalOutput,
  maxCsvLine = null,
  csvMapping = null,
  webContents
) {
  // 1) Organizza da CSV
  let csvPath = null;
  try {
    const files = await fs.readdir(dir);
    const found = files.find(f => f.toLowerCase().endsWith('.csv'));
    if (found) csvPath = path.join(dir, found);
  } catch (err) {
    logger.warn('[postprocessing] Errore lettura directory:', err.message);
  }

  logger.info(`[postprocessing] CSV Mapping: ${JSON.stringify(csvMapping)}`);
  if (csvPath) {
    logger.info(`[postprocessing] CSV trovato: ${csvPath}`);
    await organizeFromCsv(
      csvPath,
      finalOutput,
      finalOutput,
      csvProgress => webContents.send('csv:progress', csvProgress),
      maxCsvLine,
      csvMapping
    );
    logger.info(`[postprocessing] CSV processato: ${csvPath}`);
  }

  // 2) Creazione ZIP
  const organizedDir = path.join(finalOutput, 'organized');
  const organizedThumbDir = path.join(finalOutput, 'organized_thumbnails');
  const outputZip = path.join(finalOutput, 'final_output.zip');

  try {
    await fs.access(organizedDir);
    await fs.access(organizedThumbDir);
  } catch (err) {
    const msg = `Directory non trovate per ZIP: ${organizedDir}, ${organizedThumbDir}`;
    logger.error('[postprocessing]', msg);
    webContents.send('zip:error', msg);
    throw new Error(msg);
  }

  const zipWorkerPath = path.join(__dirname, 'workers', 'zip_worker.js');
  if (!fsSync.existsSync(zipWorkerPath)) {
    const msg = `Zip worker non trovato: ${zipWorkerPath}`;
    logger.error('[postprocessing]', msg);
    throw new Error(msg);
  }

  logger.info(`[postprocessing] Forking zip worker: ${zipWorkerPath}`);
  await new Promise((resolve, reject) => {
    const child = fork(
      zipWorkerPath,
      [organizedDir, organizedThumbDir, outputZip],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
      }
    );

    child.stdout.on('data', chunk => {
      const msg = chunk.toString().trim();
      logger.info(`[zip_worker stdout] ${msg}`);
      webContents.send('zip:log', msg);
    });
    child.stderr.on('data', chunk => {
      const msg = chunk.toString().trim();
      logger.error(`[zip_worker stderr] ${msg}`);
      webContents.send('zip:log', msg);
    });

    child.on('exit', code => {
      if (code === 0) {
        logger.info('[postprocessing] zip_worker exited with code 0');
        webContents.send('zip:done', outputZip);
        resolve();
      } else {
        const error = new Error(`zip_worker code ${code}`);
        logger.error('[postprocessing]', error.message);
        reject(error);
      }
    });
  });
}

