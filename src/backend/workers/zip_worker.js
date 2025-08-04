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
 * Punto di ingresso: copia le directory organizzate in un temp, crea lo zip e pulisce.
 */
async function main() {
  const [,, organizedDir, organizedThumbDir, outputZip] = process.argv;
  if (!organizedDir || !organizedThumbDir || !outputZip) {
    logger.info('Usage: node zip_worker.js <organizedDir> <organizedThumbDir> <outputZip>');
    process.exit(1);
  }

  const tmp = path.join(path.dirname(outputZip), '__tmp_zip_dir__');

  try {
    // 1. Pulisco la temp dir
    logger.info(`[zip_worker] Rimuovo temp dir: ${tmp}`);
    await fs.rm(tmp, { recursive: true, force: true });

    // 2. Copio organizedDir in tmp
    logger.info(`[zip_worker] Copio organizedDir: ${organizedDir} → ${tmp}`);
    await copyDir(organizedDir, tmp);

    // 3. Gestisco le thumbnails
    const thumbnailsDest = path.join(tmp, 'thumbnails');
    logger.info(`[zip_worker] Rimuovo eventuale thumbnails dest: ${thumbnailsDest}`);
    await fs.rm(thumbnailsDest, { recursive: true, force: true });
    logger.info(`[zip_worker] Copio organizedThumbDir: ${organizedThumbDir} → ${thumbnailsDest}`);
    await copyDir(organizedThumbDir, thumbnailsDest);

    // 4. Creo lo zip
    logger.info(`[zip_worker] Inizio creazione ZIP in: ${outputZip}`);

    await new Promise((resolve, reject) => {
      const output = fsSync.createWriteStream(outputZip, { flags: 'w' });
      const archive = archiver('zip', { zlib: { level: 9 } });

      // Log eventi del file stream
      output.on('close', () => {
        logger.info(`[zip_worker] Zip chiuso (${archive.pointer()} bytes)`);
        resolve();
      });
      output.on('end', () => {
        logger.info('[zip_worker] Output stream ended');
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
      archive.on('progress', progress => {
        const { entries } = progress;
        logger.info(`[zip_worker] Progresso: ${entries.processed} di ${entries.total} entries`);
      });
      archive.on('error', err => {
        logger.error(`[zip_worker] Errore archiver: ${err.message}`);
        reject(err);
      });
      archive.on('finish', () => {
        logger.info('[zip_worker] Archiver finish: tutti i dati inviati allo stream');
      });

      // Collego e finalizzo
      archive.pipe(output);
      logger.info(`[zip_worker] Pipe creato. Archivio directory temporanea: ${tmp}`);
      archive.directory(tmp, false);
      archive.finalize().then(() => {
        logger.info('[zip_worker] Chiamata archive.finalize() completata');
      }).catch(err => {
        logger.error(`[zip_worker] Errore finalize(): ${err.message}`);
        reject(err);
      });
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
