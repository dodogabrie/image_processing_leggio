const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const { parse } = require('csv-parse/sync');
const slugify = require('slugify');

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

      // estrai e sluggifica il titolo
      const rawTitle = row["TITOLO PER LEGGIO\nda compilare o revisionare Letizia"] || "";
      if (!rawTitle || rawTitle === "") {
        // skip the image
        console.log(`[organize_by_csv] TITOLO non trovato per codice ${codice}`);
        return;
      }
      // Sanitize slug for Windows compatibility
      const slug = slugify(rawTitle, { lower: true, strict: true, locale: 'it' });

      // crea la cartella organized/<slug>
      if (!createdOrganizedDir) {
        await fs.mkdir(organizedDir, { recursive: true });
        createdOrganizedDir = true;
      }
      const destDir = path.join(organizedDir, slug);
      const dest    = path.join(destDir, `${slug}_${codice}.webp`);
      await fs.mkdir(destDir, { recursive: true });
      try {
        await fs.copyFile(src, dest);
        await fs.access(dest);
        if (!fsSync.existsSync(dest)) {
          console.error(`[organize_by_csv] ERRORE: file non trovato dopo copia: ${dest}`);
        }
      } catch (err) {
        console.error(`[organize_by_csv] Errore su file ${src} -> ${dest}: ${err.message}`);
        throw err;
      }
      copiedAny = true;

      // --- THUMBNAIL ORGANIZATION usando la stessa slug e stesso nome file + alias ---
      const thumbnailsRoot = path.join(webpDir, 'thumbnails');
      const relFolder      = path.relative(webpDir, targetFolderPath);
      const thumbSrcDir    = path.join(thumbnailsRoot, relFolder);
      const thumbBaseName  = `${slug}_${codice}`; // stesso nome del file organizzato senza estensione
      const thumbAliases   = ['low_quality', 'gallery'];

      if (!createdOrganizedThumbDir) {
        await fs.mkdir(organizedThumbDir, { recursive: true });
        createdOrganizedThumbDir = true;
      }
      const thumbDestDir = path.join(organizedThumbDir, slug);
      await fs.mkdir(thumbDestDir, { recursive: true });

      for (const alias of thumbAliases) {
        const srcThumb  = path.join(thumbSrcDir, `${id0}_${id1}_${id2}_${alias}.webp`);
        const destThumb = path.join(thumbDestDir, `${thumbBaseName}_${alias}.webp`);
        try {
          await fs.copyFile(srcThumb, destThumb);
          await fs.access(destThumb);
          if (!fsSync.existsSync(destThumb)) {
            console.error(`[organize_by_csv] ERRORE: thumbnail non trovata dopo copia: ${destThumb}`);
          }
        } catch (err) {
          console.log(`[organize_by_csv] Thumbnail non trovato: ${srcThumb}`);
        }
      }

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
      await fs.access(destCsv);
      if (!fsSync.existsSync(destCsv)) {
        console.error(`[organize_by_csv] ERRORE: CSV non trovato dopo copia: ${destCsv}`);
      }
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
      await fs.access(destCsv);
      if (!fsSync.existsSync(destCsv)) {
        console.error(`[organize_by_csv] ERRORE: CSV organized_thumbnails non trovato dopo copia: ${destCsv}`);
      }
      console.log(`[organize_by_csv] Copiato anche il CSV in: ${destCsv}`);
    } catch (err) {
      console.error(`[organize_by_csv] Errore copia CSV organized_thumbnails:`, err.message);
    }
  }
}

module.exports = { organizeFromCsv };

