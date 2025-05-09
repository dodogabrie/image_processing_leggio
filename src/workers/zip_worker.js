const fs = require('fs').promises;
const path = require('path');
const archiver = require('archiver');
const fsSync = require('fs');

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

async function main() {
  const [,, organizedDir, organizedThumbDir, outputZip] = process.argv;
  if (!organizedDir || !organizedThumbDir || !outputZip) {
    console.error('Usage: node zip_worker.js <organizedDir> <organizedThumbDir> <outputZip>');
    process.exit(1);
  }

  // Crea una cartella temporanea per la struttura finale
  const tmp = path.join(path.dirname(outputZip), '__tmp_zip_dir__');
  try {
    console.log(`[zip_worker] Rimuovo tmp dir: ${tmp}`);
    await fs.rm(tmp, { recursive: true, force: true });

    console.log(`[zip_worker] Copio organizedDir: ${organizedDir} -> ${tmp}`);
    await copyDir(organizedDir, tmp);

    // Copia organized_thumbnails come "thumbnails" dentro tmp
    const thumbnailsDest = path.join(tmp, 'thumbnails');
    console.log(`[zip_worker] Rimuovo thumbnails dest: ${thumbnailsDest}`);
    await fs.rm(thumbnailsDest, { recursive: true, force: true });

    console.log(`[zip_worker] Copio organizedThumbDir: ${organizedThumbDir} -> ${thumbnailsDest}`);
    await copyDir(organizedThumbDir, thumbnailsDest);

    // Crea lo zip
    console.log(`[zip_worker] Creo lo zip: ${outputZip}`);
    await new Promise((resolve, reject) => {
      const output = fsSync.createWriteStream(outputZip, { flags: 'w' });
      const archive = archiver('zip', { zlib: { level: 9 } });

      let finalized = false;
      output.on('close', () => {
        console.log(`[zip_worker] Zip chiuso (${archive.pointer()} bytes)`);
        if (finalized) resolve();
      });
      output.on('error', (err) => {
        console.error(`[zip_worker] Errore stream output: ${err.message}`);
        reject(err);
      });
      archive.on('error', (err) => {
        console.error(`[zip_worker] Errore archiver: ${err.message}`);
        reject(err);
      });

      archive.pipe(output);
      archive.directory(tmp, false);

      archive.finalize().then(() => {
        finalized = true;
        console.log('[zip_worker] archive.finalize() completato');
        if (output.closed || output.destroyed) resolve();
      }).catch((err) => {
        console.error(`[zip_worker] Errore finalize: ${err.message}`);
        reject(err);
      });
    });

    // Pulisci la cartella temporanea
    console.log(`[zip_worker] Rimuovo tmp dir finale: ${tmp}`);
    await fs.rm(tmp, { recursive: true, force: true });
    console.log('[zip_worker] Completato con successo');
    process.exit(0);
  } catch (err) {
    console.error('Errore zip_worker:', err.message);
    try { await fs.rm(tmp, { recursive: true, force: true }); } catch {}
    process.exit(2);
  }
}

main();
