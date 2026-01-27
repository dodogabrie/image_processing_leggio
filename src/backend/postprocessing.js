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
const __dirname = dirname(__filename);
const logger = new Logger();

/**
 * Ricopia ricorsivamente una directory.
 * @param {string} src - Directory di origine.
 * @param {string} dest - Directory di destinazione.
 */
async function copyDir(src, dest) {
  await fs.mkdir(dest, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDir(srcPath, destPath);
    } else {
      await fs.copyFile(srcPath, destPath);
    }
  }
}

/**
 * Esegue post-processing: ordinamento da CSV (se presente) e creazione ZIP.
 * @param {string} dir - Directory di input (contenente eventuale CSV).
 * @param {string} finalOutput - Directory di output per organizzati e ZIP.
 * @param {number|null} maxCsvLine - Numero massimo di righe CSV da processare.
 * @param {Object|null} csvMapping - Mappatura colonne CSV.
 * @param {Electron.WebContents} webContents - Canale per invio progress log.
 * @param {string} webpSourceDir - Directory da cui leggere le immagini (può essere diversa da finalOutput se si salta l'ottimizzazione)
 * @throws Error in caso di fallimento.
 */
export async function postProcessResults(
  dir,
  finalOutput,
  maxCsvLine = null,
  csvMapping = null,
  webContents,
  webpSourceDir = finalOutput
) {
  // 1) Organizza da CSV
  let csvPath = null;
  try {
    const files = await fs.readdir(dir);
    const found = files.find(f => {
      const lower = f.toLowerCase();
      return lower.endsWith('.csv') || lower.endsWith('.xlsx');
    });
    if (found) csvPath = path.join(dir, found);
  } catch (err) {
    logger.warn('[postprocessing] Errore lettura directory:', err.message);
  }

  logger.info(`[postprocessing] CSV Mapping: ${JSON.stringify(csvMapping)}`);
  if (csvPath) {
    logger.info(`[postprocessing] CSV trovato: ${csvPath}`);
    await organizeFromCsv(
      csvPath,
      webpSourceDir,
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
  const thumbnailsDir = path.join(finalOutput, 'thumbnails');
  const outputZip = path.join(finalOutput, 'output.zip');

  // Verifica se esistono le directory organizzate
  let organizedExists = false;
  let organizedThumbExists = false;
  
  try {
    await fs.access(organizedDir);
    organizedExists = true;
  } catch {}
  
  try {
    await fs.access(organizedThumbDir);
    organizedThumbExists = true;
  } catch {}

  // Se non esistono le cartelle organizzate, le creiamo
  if (!organizedExists || !organizedThumbExists) {
    logger.info('[postprocessing] Cartelle organizzate non trovate, creo da contenuto directory');
    
    if (!organizedExists) {
      // Crea organized copiando tutto tranne thumbnails
      await fs.mkdir(organizedDir, { recursive: true });
      const entries = await fs.readdir(webpSourceDir, { withFileTypes: true });
      
      for (const entry of entries) {
        if (entry.name === 'thumbnails' || entry.name === 'organized' || entry.name === 'organized_thumbnails') {
          continue; // Salta thumbnails e cartelle organizzate
        }
        
        const srcPath = path.join(webpSourceDir, entry.name);
        const destPath = path.join(organizedDir, entry.name);
        
        if (entry.isDirectory()) {
          await copyDir(srcPath, destPath);
        } else {
          await fs.copyFile(srcPath, destPath);
        }
        logger.info(`[postprocessing] Copiato in organized: ${entry.name}`);
      }
    }
    
    if (!organizedThumbExists) {
      // Usa la cartella thumbnails esistente come organized_thumbnails
      try {
        await fs.access(thumbnailsDir);
        await fs.rename(thumbnailsDir, organizedThumbDir);
        logger.info(`[postprocessing] Rinominata ${thumbnailsDir} → ${organizedThumbDir}`);
      } catch (err) {
        // Se non esiste thumbnails, crea una cartella vuota
        await fs.mkdir(organizedThumbDir, { recursive: true });
        logger.warn(`[postprocessing] Cartella thumbnails non trovata, creata cartella vuota: ${organizedThumbDir}`);
      }
    }
  }

  const zipWorkerPath = path.join(__dirname, 'workers', 'zip_worker.js');
  if (!fsSync.existsSync(zipWorkerPath)) {
    const msg = `Zip worker non trovato: ${zipWorkerPath}`;
    logger.error('[postprocessing]', msg);
    throw new Error(msg);
  }

  logger.info(`[postprocessing] Forking zip worker: ${zipWorkerPath}`);
  webContents.send('zip:log', 'Creazione ZIP in corso, attendere il completamento...');
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
