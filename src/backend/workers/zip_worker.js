import fs from 'fs/promises';
import * as fsSync from 'fs';
import path from 'path';
import archiver from 'archiver';
import Logger from '../Logger.js';

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
      logger.info(`[zip_worker] Copiata: ${srcPath} → ${destPath}`);
    }
  }
}

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
async function createSingleZip(sourceDir, outputPath, maxSizeBytes = 1024 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const output = fsSync.createWriteStream(outputPath, { flags: 'w' });
    const archive = archiver('zip', { zlib: { level: 9 } });
    let currentSize = 0;
    let aborted = false;

    // Log eventi del file stream
    output.on('close', () => {
      if (!aborted) {
        logger.info(`[zip_worker] Zip chiuso: ${outputPath} (${archive.pointer()} bytes)`);
        resolve({ success: true, sizeBytes: archive.pointer() });
      }
    });
    
    output.on('error', err => {
      logger.error(`[zip_worker] Errore stream output: ${err.message}`);
      reject(err);
    });

    // Log eventi archiver
    archive.on('entry', entry => {
      currentSize += entry.stats.size || 0;
      logger.info(`[zip_worker] Entry aggiunto: ${entry.name} (${currentSize} bytes totali)`);
      
      // Controlla se abbiamo superato il limite
      if (currentSize > maxSizeBytes && !aborted) {
        logger.warn(`[zip_worker] Limite dimensione raggiunto (${currentSize} > ${maxSizeBytes}), interrompo archivio`);
        aborted = true;
        archive.abort();
        output.destroy();
        resolve({ success: false, sizeBytes: currentSize });
      }
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
    logger.info(`[zip_worker] Archivio directory: ${sourceDir} → ${outputPath}`);
    archive.directory(sourceDir, false);
    archive.finalize().then(() => {
      if (!aborted) {
        logger.info(`[zip_worker] Archivio completato: ${outputPath}`);
      }
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
async function createMultipartZips(sourceDir, baseOutputPath, maxSizeBytes = 1024 * 1024 * 1024) {
  const baseName = baseOutputPath.split('.zip')[0];
  let partNumber = 1;
  const createdZips = [];

  // Ottieni lista di tutti i file/directory nella sourceDir
  const entries = await fs.readdir(sourceDir, { withFileTypes: true });
  
  if (entries.length === 0) {
    logger.warn(`[zip_worker] Directory vuota: ${sourceDir}, creo ZIP vuoto`);
    const emptyZipPath = `${baseName}.zip`;
    await createSingleZip(sourceDir, emptyZipPath, maxSizeBytes);
    return [emptyZipPath];
  }

  // Prova prima con tutto insieme
  const fullZipPath = partNumber === 1 ? `${baseName}.zip` : `${baseName}_part${partNumber}.zip`;
  logger.info(`[zip_worker] Tentativo creazione ZIP completo: ${fullZipPath}`);
  
  const result = await createSingleZip(sourceDir, fullZipPath, maxSizeBytes);
  
  if (result.success) {
    // Tutto è entrato in un singolo ZIP
    logger.info(`[zip_worker] Archivio completo creato con successo: ${fullZipPath}`);
    createdZips.push(fullZipPath);
  } else {
    // Dobbiamo dividere in parti
    logger.info(`[zip_worker] Archivio troppo grande, divido in parti multiple`);
    
    // Rimuovi il ZIP parziale fallito
    try {
      await fs.unlink(fullZipPath);
    } catch {}

    // Crea ZIP separati per ogni entry principale
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i];
      const entryPath = path.join(sourceDir, entry.name);
      const partZipPath = `${baseName}_part${partNumber}.zip`;
      
      // Crea directory temporanea per questa parte
      const partTmpDir = path.join(path.dirname(sourceDir), `__tmp_part_${partNumber}__`);
      await fs.mkdir(partTmpDir, { recursive: true });
      
      try {
        const partDestPath = path.join(partTmpDir, entry.name);
        if (entry.isDirectory()) {
          await copyDir(entryPath, partDestPath);
        } else {
          await fs.copyFile(entryPath, partDestPath);
        }
        
        logger.info(`[zip_worker] Creazione parte ${partNumber}: ${partZipPath}`);
        const partResult = await createSingleZip(partTmpDir, partZipPath, maxSizeBytes);
        
        if (partResult.success) {
          createdZips.push(partZipPath);
          logger.info(`[zip_worker] Parte ${partNumber} completata con successo`);
        } else {
          logger.error(`[zip_worker] Parte ${partNumber} ancora troppo grande, potrebbe essere necessaria divisione ulteriore`);
          // Per ora creiamo comunque il file, in futuro si potrebbe implementare divisione ricorsiva
          createdZips.push(partZipPath);
        }
        
        partNumber++;
      } finally {
        // Pulisci directory temporanea della parte
        await fs.rm(partTmpDir, { recursive: true, force: true });
      }
    }
  }
  
  return createdZips;
}

/**
 * Punto di ingresso: copia le directory organizzate in un temp, crea lo zip e pulisce.
 */
async function main() {
  const [,, organizedDir, organizedThumbDir, outputZip] = process.argv;
  if (!organizedDir || !organizedThumbDir || !outputZip) {
    logger.info('Usage: node zip_worker.js <organizedDir> <organizedThumbDir> <outputZip>');
    process.exit(1);
  }

  const tmp = path.join(path.dirname(outputZip), '__tmp_zip_dir__');
  const maxZipSize = 1024 * 1024 * 1024; // 1GB

  try {
    // 1. Pulisco la temp dir
    logger.info(`[zip_worker] Rimuovo temp dir: ${tmp}`);
    await fs.rm(tmp, { recursive: true, force: true });

    // 2. Verifico se organizedDir esiste e lo copio
    const organizedExists = await dirExists(organizedDir);
    if (organizedExists) {
      logger.info(`[zip_worker] Copio organizedDir: ${organizedDir} → ${tmp}`);
      await copyDir(organizedDir, tmp);
    } else {
      logger.warn(`[zip_worker] Directory organizzata non trovata: ${organizedDir}, creo directory vuota`);
      await fs.mkdir(tmp, { recursive: true });
    }

    // 3. Gestisco le thumbnails
    const thumbnailsExists = await dirExists(organizedThumbDir);
    const thumbnailsDest = path.join(tmp, 'thumbnails');
    
    if (thumbnailsExists) {
      logger.info(`[zip_worker] Rimuovo eventuale thumbnails dest: ${thumbnailsDest}`);
      await fs.rm(thumbnailsDest, { recursive: true, force: true });
      logger.info(`[zip_worker] Copio organizedThumbDir: ${organizedThumbDir} → ${thumbnailsDest}`);
      await copyDir(organizedThumbDir, thumbnailsDest);
    } else {
      logger.warn(`[zip_worker] Directory thumbnails non trovata: ${organizedThumbDir}, creo directory vuota`);
      await fs.mkdir(thumbnailsDest, { recursive: true });
    }

    // 4. Creo gli ZIP con limite di dimensione
    logger.info(`[zip_worker] Inizio creazione ZIP con limite ${maxZipSize / (1024*1024*1024)}GB`);
    
    const createdZips = await createMultipartZips(tmp, outputZip, maxZipSize);
    
    logger.info(`[zip_worker] Creati ${createdZips.length} file ZIP:`);
    createdZips.forEach((zipPath, index) => {
      logger.info(`[zip_worker]   ${index + 1}. ${zipPath}`);
    });

    // 5. Pulisco la temp dir finale
    logger.info(`[zip_worker] Rimuovo temp dir dopo ZIP: ${tmp}`);
    await fs.rm(tmp, { recursive: true, force: true });
    logger.info('[zip_worker] Operazione completata con successo');
    process.exit(0);

  } catch (err) {
    logger.error('[zip_worker] Errore generale:', err.message);
    // Provo a pulire comunque
    try { await fs.rm(tmp, { recursive: true, force: true }); } catch {}
    process.exit(2);
  }
}

main();
