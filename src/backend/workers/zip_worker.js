import fs from 'fs/promises';
import * as fsSync from 'fs';
import path from 'path';
import archiver from 'archiver';
import Logger from '../Logger.js';

const logger = new Logger();

/**
 * Verifica se una directory esiste.
 * @param {string} dirPath - Percorso della directory.
 * @returns {boolean} - True se esiste, false altrimenti.
 */
async function dirExists(dirPath) {
  try {
    const stat = await fs.stat(dirPath);
    return stat.isDirectory();
  } catch {
    return false;
  }
}

/**
 * Crea un singolo file ZIP con limite di dimensione massima.
 * @param {string} sourceDir - Directory da archiviare
 * @param {string} outputPath - Percorso del file ZIP
 * @param {number} maxSizeBytes - Dimensione massima in bytes (default 1GB)
 * @returns {Promise<{success: boolean, sizeBytes: number}>}
 */
async function createSingleZip(sourceDir, outputPath, maxSizeBytes = 1024 * 1024 * 1024, thumbnailsDir = null) {
  return new Promise((resolve, reject) => {
    const output = fsSync.createWriteStream(outputPath, { flags: 'w' });
    const archive = archiver('zip', { zlib: { level: 9 } });

    // Log eventi del file stream
    output.on('close', () => {
      try {
        const finalSize = fsSync.statSync(outputPath).size;
        logger.info(`[zip_worker] Zip chiuso: ${outputPath} (${finalSize} bytes)`);
        resolve({ success: true, sizeBytes: finalSize });
      } catch (err) {
        logger.error(`[zip_worker] Errore stat zip: ${err.message}`);
        reject(err);
      }
    });
    
    output.on('error', err => {
      logger.error(`[zip_worker] Errore stream output: ${err.message}`);
      reject(err);
    });

    // Log eventi archiver
    archive.on('entry', entry => {
      logger.info(`[zip_worker] Entry aggiunto: ${entry.name}`);
    });

    archive.on('warning', warn => {
      logger.warn(`[zip_worker] Warning archiver: ${warn.message}`);
    });

    archive.on('error', err => {
      logger.error(`[zip_worker] Errore archiver: ${err.message}`);
      reject(err);
    });

    // Collego e finalizzo
    archive.pipe(output);
    logger.info(`[zip_worker] Archivio ZIP: ${outputPath}`);
    if (sourceDir) {
      archive.directory(sourceDir, false);
      logger.info(`[zip_worker]   + directory: ${sourceDir}`);
    }
    if (thumbnailsDir) {
      archive.directory(thumbnailsDir, 'thumbnails');
      logger.info(`[zip_worker]   + thumbnails: ${thumbnailsDir}`);
    }
    archive.finalize().then(() => {
      logger.info(`[zip_worker] Archivio completato: ${outputPath}`);
    }).catch(err => {
      logger.error(`[zip_worker] Errore finalize(): ${err.message}`);
      reject(err);
    });
  });
}

/**
 * Divide i contenuti di una directory in più ZIP se necessario.
 * @param {string} sourceDir - Directory da archiviare
 * @param {string} baseOutputPath - Percorso base per i file ZIP
 * @param {number} maxSizeBytes - Dimensione massima per ZIP
 */
async function createMultipartZips(sourceDir, baseOutputPath, maxSizeBytes = 1024 * 1024 * 1024, thumbnailsDir = null) {
  const baseName = baseOutputPath.split('.zip')[0];
  const createdZips = [];

  // Ottieni lista di tutti i file/directory nella sourceDir
  const entries = sourceDir ? await fs.readdir(sourceDir, { withFileTypes: true }) : [];
  
  if (entries.length === 0) {
    logger.warn(`[zip_worker] Directory vuota: ${sourceDir || '(none)'}, creo ZIP vuoto`);
    const emptyZipPath = `${baseName}.zip`;
    await createSingleZip(sourceDir, emptyZipPath, maxSizeBytes, thumbnailsDir);
    return [emptyZipPath];
  }

  // Prova prima con tutto insieme
  const fullZipPath = `${baseName}.zip`;
  logger.info(`[zip_worker] Tentativo creazione ZIP completo: ${fullZipPath}`);
  
  const result = await createSingleZip(sourceDir, fullZipPath, maxSizeBytes, thumbnailsDir);
  
  if (result.success && result.sizeBytes <= maxSizeBytes) {
    // Tutto è entrato in un singolo ZIP
    logger.info(`[zip_worker] Archivio completo creato con successo: ${fullZipPath}`);
    createdZips.push(fullZipPath);
  } else {
    // Dobbiamo dividere in parti
    logger.info(`[zip_worker] Archivio troppo grande (${result.sizeBytes} > ${maxSizeBytes}), divido in parti multiple`);
    
    // Rimuovi il ZIP parziale fallito
    try {
      await fs.unlink(fullZipPath);
    } catch {}

    const packedZips = await packEntriesIntoZips(entries, sourceDir, thumbnailsDir, baseName, maxSizeBytes);
    createdZips.push(...packedZips);
  }
  
  return createdZips;
}

/**
 * Crea uno ZIP con una lista di entries (file/dir) alla root e le thumbnails correlate.
 * @param {Array<{name: string, path: string, isDirectory: boolean}>} entries
 */
async function createZipForEntries(entries, outputPath, thumbnailsDir = null) {
  return new Promise((resolve, reject) => {
    const output = fsSync.createWriteStream(outputPath, { flags: 'w' });
    const archive = archiver('zip', { zlib: { level: 9 } });

    output.on('close', () => {
      try {
        const finalSize = fsSync.statSync(outputPath).size;
        logger.info(`[zip_worker] Zip chiuso: ${outputPath} (${finalSize} bytes)`);
        resolve({ success: true, sizeBytes: finalSize });
      } catch (err) {
        logger.error(`[zip_worker] Errore stat zip: ${err.message}`);
        reject(err);
      }
    });
    
    output.on('error', err => {
      logger.error(`[zip_worker] Errore stream output: ${err.message}`);
      reject(err);
    });

    archive.on('entry', entry => {
      logger.info(`[zip_worker] Entry aggiunto: ${entry.name}`);
    });

    archive.on('warning', warn => {
      logger.warn(`[zip_worker] Warning archiver: ${warn.message}`);
    });

    archive.on('error', err => {
      logger.error(`[zip_worker] Errore archiver: ${err.message}`);
      reject(err);
    });

    archive.pipe(output);
    logger.info(`[zip_worker] Archivio parte: ${outputPath} (${entries.length} entries)`);

    for (const entry of entries) {
      if (entry.isDirectory) {
        archive.directory(entry.path, entry.name);
      } else {
        archive.file(entry.path, { name: entry.name });
      }

      if (thumbnailsDir) {
        const thumbPath = path.join(thumbnailsDir, entry.name);
        if (fsSync.existsSync(thumbPath)) {
          archive.directory(thumbPath, path.join('thumbnails', entry.name));
        }
      }
    }

    archive.finalize().then(() => {
      logger.info(`[zip_worker] Archivio completato: ${outputPath}`);
    }).catch(err => {
      logger.error(`[zip_worker] Errore finalize(): ${err.message}`);
      reject(err);
    });
  });
}

/**
 * Bin-packing: riempie i ZIP fino al limite usando ricerca binaria sul prefisso.
 * Controllo basato sulla dimensione finale del file ZIP.
 */
async function packEntriesIntoZips(entries, sourceDir, thumbnailsDir, baseName, maxSizeBytes) {
  const normalized = entries.map(entry => ({
    name: entry.name,
    path: path.join(sourceDir, entry.name),
    isDirectory: entry.isDirectory()
  }));

  let index = 0;
  let partNumber = 1;
  const created = [];

  while (index < normalized.length) {
    let lo = 1;
    let hi = normalized.length - index;
    let best = 0;
    let bestTmpPath = null;

    while (lo <= hi) {
      const mid = Math.floor((lo + hi) / 2);
      const slice = normalized.slice(index, index + mid);
      const tmpPath = `${baseName}_part${partNumber}_tmp.zip`;

      const result = await createZipForEntries(slice, tmpPath, thumbnailsDir);

      if (result.sizeBytes <= maxSizeBytes) {
        if (bestTmpPath && bestTmpPath !== tmpPath) {
          try { await fs.unlink(bestTmpPath); } catch {}
        }
        best = mid;
        bestTmpPath = tmpPath;
        lo = mid + 1;
      } else {
        try { await fs.unlink(tmpPath); } catch {}
        hi = mid - 1;
      }
    }

    if (best === 0) {
      // Singola entry troppo grande: crea ZIP oversize
      const oversizeEntry = normalized[index];
      const oversizePath = `${baseName}_part${partNumber}_oversize.zip`;
      const oversizeResult = await createZipForEntries([oversizeEntry], oversizePath, thumbnailsDir);
      created.push(oversizePath);
      logger.warn(
        `[zip_worker] Creato ZIP oversize ${oversizePath} (${oversizeResult.sizeBytes} bytes)`
      );
      index += 1;
      partNumber += 1;
      continue;
    }

    const finalPath = `${baseName}_part${partNumber}.zip`;
    let finalizedPath = finalPath;
    if (bestTmpPath && bestTmpPath !== finalPath) {
      try {
        await fs.rename(bestTmpPath, finalPath);
      } catch (err) {
        // Fallback to copy + unlink if rename fails
        logger.warn(`[zip_worker] Rename fallito (${bestTmpPath} → ${finalPath}): ${err.message}`);
        try {
          await fs.copyFile(bestTmpPath, finalPath);
          await fs.unlink(bestTmpPath);
        } catch (copyErr) {
          logger.error(`[zip_worker] Copy fallback fallita: ${copyErr.message}`);
          // Keep temp as final to avoid losing the part
          finalizedPath = bestTmpPath;
        }
      }
    }
    created.push(finalizedPath);
    logger.info(`[zip_worker] Parte ${partNumber} completata (${best} entries) → ${finalizedPath}`);

    index += best;
    partNumber += 1;
  }

  return created;
}

/**
 * Crea uno ZIP con una singola entry principale e (opzionalmente) le sue thumbnails.
 * @param {string} entryPath
 * @param {string} entryName
 * @param {string} outputPath
 * @param {number} maxSizeBytes
 * @param {string|null} thumbnailsEntryDir
 * @param {boolean} isDirectory
 */

/**
 * Punto di ingresso: crea lo zip direttamente dalle directory organizzate.
 */
async function main() {
  const [,, organizedDir, organizedThumbDir, outputZip] = process.argv;
  if (!organizedDir || !organizedThumbDir || !outputZip) {
    logger.info('Usage: node zip_worker.js <organizedDir> <organizedThumbDir> <outputZip>');
    process.exit(1);
  }

  const maxZipSize = 1024 * 1024 * 1024; // 1GB

  try {
    // 1. Verifico se organizedDir esiste
    const organizedExists = await dirExists(organizedDir);
    if (organizedExists) {
      logger.info(`[zip_worker] organizedDir trovato: ${organizedDir}`);
    } else {
      logger.warn(`[zip_worker] Directory organizzata non trovata: ${organizedDir}, creo directory vuota`);
    }

    // 2. Gestisco le thumbnails
    const thumbnailsExists = await dirExists(organizedThumbDir);
    if (thumbnailsExists) {
      logger.info(`[zip_worker] organizedThumbDir trovato: ${organizedThumbDir}`);
    } else {
      logger.warn(`[zip_worker] Directory thumbnails non trovata: ${organizedThumbDir}, creo directory vuota`);
    }

    // 3. Creo gli ZIP con limite di dimensione
    logger.info(`[zip_worker] Inizio creazione ZIP con limite ${maxZipSize / (1024*1024*1024)}GB`);
    
    // Crea zip direttamente dalle directory sorgenti
    const createdZips = await createMultipartZips(
      organizedExists ? organizedDir : null,
      outputZip,
      maxZipSize,
      thumbnailsExists ? organizedThumbDir : null
    );
    
    logger.info(`[zip_worker] Creati ${createdZips.length} file ZIP:`);
    createdZips.forEach((zipPath, index) => {
      logger.info(`[zip_worker]   ${index + 1}. ${zipPath}`);
    });

    logger.info('[zip_worker] Operazione completata con successo');
    process.exit(0);

  } catch (err) {
    logger.error('[zip_worker] Errore generale:', err.message);
    process.exit(2);
  }
}

main();
