const fs = require('fs').promises;
const path = require('path');
const { parse } = require('csv-parse/sync');

async function findSubfolderRecursive(rootDir, prefix) {
  const entries = await fs.readdir(rootDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (entry.name.startsWith(prefix)) {
        return path.join(rootDir, entry.name);
      }
      const found = await findSubfolderRecursive(path.join(rootDir, entry.name), prefix);
      if (found) return found;
    }
  }
  return null;
}

async function organizeFromCsv(csvPath, webpDir, outputDir, progressCallback = () => {}, maxLine = null) {
  try {
    await fs.access(csvPath);
  } catch {
    console.log('[organize_by_csv] Nessun CSV trovato:', csvPath);
    return;
  }

  const content = await fs.readFile(csvPath);
  let records = parse(content, { columns: true, skip_empty_lines: true });

  // Limita il numero di righe se maxLine è specificato
  console.log('maxLine:', maxLine);
  if (maxLine !== null) {
    const n = parseInt(maxLine, 10);
    if (!isNaN(n) && n > 0) {
      records = records.slice(0, n);
      console.log(`[organize_by_csv] Limito a ${n} righe del CSV (records totali: ${records.length})`);
    }
  }

  let organizedDir = path.join(outputDir, 'organized');
  let organizedThumbDir = path.join(outputDir, 'organized_thumbnails');
  let createdOrganizedDir = false;
  let createdOrganizedThumbDir = false;
  let copiedAny = false;

  const total = records.length;
  let current = 0;

  // Batch parallelo (max 4)
  const BATCH_SIZE = 4;
  let tasks = [];

  for (const row of records) {
    tasks.push(async () => {
      let codice = row["Codice"] || Object.values(row)[0] || "";
      codice = codice.trim();
      if (!codice) return;

      const match = codice.match(/^(\d+)_([\d]+)_([\d]+)$/);
      if (!match) {
        console.log(`[organize_by_csv] Codice non valido: ${codice}`);
        return;
      }
      const [_, id0, id1, id2] = match;

      const prefix = `${id0}_${id1}`;
      let targetFolderPath;
      try {
        targetFolderPath = await findSubfolderRecursive(webpDir, prefix);
      } catch (err) {
        console.log(`[organize_by_csv] Errore ricerca ricorsiva in ${webpDir}:`, err.message);
        return;
      }
      if (!targetFolderPath) {
        console.log(`[organize_by_csv] Nessuna cartella trovata per prefix ${prefix} in ${webpDir}`);
        return;
      }

      const src = path.join(targetFolderPath, `${id0}_${id1}_${id2}.webp`);
      try {
        await fs.access(src);
      } catch {
        console.log(`[organize_by_csv] File non trovato: ${src}`);
        return;
      }

      // Crea la cartella organized solo se serve
      if (!createdOrganizedDir) {
        await fs.mkdir(organizedDir, { recursive: true });
        createdOrganizedDir = true;
      }

      const destDir = path.join(organizedDir, codice);
      const dest = path.join(destDir, `${codice}.webp`);

      try {
        await fs.mkdir(destDir, { recursive: true });
        await fs.copyFile(src, dest);
        copiedAny = true;
      } catch (err) {
        console.error(`[organize_by_csv] Errore con ${codice}:`, err.message);
      }

      // --- THUMBNAIL ORGANIZATION ---
      // thumbnails are in: <webpDir>/thumbnails/<relative_path>/<basename>_<alias>.webp
      // we want: <outputDir>/organized_thumbnails/<codice>/<codice>_<alias>.webp
      const thumbnailsRoot = path.join(webpDir, 'thumbnails');
      // Ricava il path relativo della cartella dove si trova il file sorgente
      const relFolder = path.relative(webpDir, targetFolderPath);
      const thumbSourceDir = path.join(thumbnailsRoot, relFolder);
      const thumbBaseName = `${id0}_${id1}_${id2}`;
      const thumbAliases = ['low_quality', 'gallery'];
      const thumbDestDir = path.join(organizedThumbDir, codice);

      try {
        await fs.mkdir(thumbDestDir, { recursive: true });
        createdOrganizedThumbDir = true;
        for (const alias of thumbAliases) {
          const thumbSrc = path.join(thumbSourceDir, `${thumbBaseName}_${alias}.webp`);
          const thumbDest = path.join(thumbDestDir, `${codice}_${alias}.webp`);
          try {
            await fs.copyFile(thumbSrc, thumbDest);
          } catch {
            // Se la thumbnail non esiste, ignora
          }
        }
      } catch (err) {
        console.error(`[organize_by_csv] Errore copia thumbnail per ${codice}:`, err.message);
      }
      // --- END THUMBNAIL ORGANIZATION ---

      current++;
      progressCallback({
        current,
        total,
        codice,
        src,
        dest
      });
    });
  }

  // Esegui i task in batch paralleli
  async function runBatches(tasks, batchSize) {
    let idx = 0;
    while (idx < tasks.length) {
      await Promise.all(tasks.slice(idx, idx + batchSize).map(fn => fn()));
      idx += batchSize;
    }
  }
  await runBatches(tasks, BATCH_SIZE);

  // Copia anche il CSV nella cartella organized se almeno un file è stato copiato
  if (createdOrganizedDir && copiedAny) {
    const destCsv = path.join(organizedDir, path.basename(csvPath));
    try {
      await fs.copyFile(csvPath, destCsv);
      console.log(`[organize_by_csv] Copiato anche il CSV in: ${destCsv}`);
    } catch (err) {
      console.error(`[organize_by_csv] Errore copia CSV:`, err.message);
    }
  }
  // Copia anche il CSV nella cartella organized_thumbnails se almeno una thumb è stata copiata
  if (createdOrganizedThumbDir && copiedAny) {
    const destCsv = path.join(organizedThumbDir, path.basename(csvPath));
    try {
      await fs.copyFile(csvPath, destCsv);
      console.log(`[organize_by_csv] Copiato anche il CSV in: ${destCsv}`);
    } catch (err) {
      console.error(`[organize_by_csv] Errore copia CSV organized_thumbnails:`, err.message);
    }
  }
}

module.exports = { organizeFromCsv };

