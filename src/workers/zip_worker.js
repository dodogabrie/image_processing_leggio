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
    await fs.rm(tmp, { recursive: true, force: true });
    await copyDir(organizedDir, tmp);
    // Copia organized_thumbnails come "thumbnails" dentro tmp
    const thumbnailsDest = path.join(tmp, 'thumbnails');
    await fs.rm(thumbnailsDest, { recursive: true, force: true });
    await copyDir(organizedThumbDir, thumbnailsDest);

    // Crea lo zip
    await new Promise((resolve, reject) => {
      const output = fsSync.createWriteStream(outputZip);
      const archive = archiver('zip', { zlib: { level: 9 } });
      output.on('close', resolve);
      archive.on('error', reject);
      archive.pipe(output);
      archive.directory(tmp, false);
      archive.finalize();
    });

    // Pulisci la cartella temporanea
    await fs.rm(tmp, { recursive: true, force: true });
    process.exit(0);
  } catch (err) {
    console.error('Errore zip_worker:', err.message);
    try { await fs.rm(tmp, { recursive: true, force: true }); } catch {}
    process.exit(2);
  }
}

main();
