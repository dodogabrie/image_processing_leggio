// File: backend/workers/organize_by_csv.js
import fs from 'fs/promises';
import * as fsSync from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import slugify from 'slugify';
import Logger from '../Logger.js';

const logger = new Logger();

// Campi speciali che non devono essere processati per le lingue
const SPECIAL_FIELDS = ['identifier', 'groupBy', 'active', 'date', 'language', 'metadata_available', 'metadata_just_year'];

/**
 * Flattens a nested mapping object into flat key paths.
 * @param {{ document: Object, image: Object }} mapping - Nested mapping
 * @returns {{ document: Record<string,string>, image: Record<string,string> }} - Flat mapping
 */
function flattenMapping(mapping) {
  const out = { document: {}, image: {} };
  for (const section of ['document', 'image']) {
    const secObj = mapping[section] || {};
    for (const [key, val] of Object.entries(secObj)) {
      if (val != null && typeof val === 'object' && !Array.isArray(val)) {
        for (const [subKey, subVal] of Object.entries(val)) {
          out[section][`${key}.${subKey}`] = String(subVal ?? '').trim();
        }
      } else {
        out[section][key] = String(val ?? '').trim();
      }
    }
  }
  return out;
}

/**
 * Estrae valori multi-lingua da un record, raggruppandoli per prefisso
 * @param {Object} record - Il record da cui estrarre i valori
 * @param {Array<string>} availableFields - Elenco dei campi disponibili
 * @returns {Object} - Oggetto con valori raggruppati per lingua
 */
function extractLangValues(record, availableFields) {
  const langGroups = {};
  availableFields.forEach(field => {
    const value = record[field];
    if (value != null && value !== '') {
      // Formato con underscore: prefix_lang
      if (field.includes('_')) {
        const [prefix, lang] = field.split('_', 2);
        if (lang) {
          langGroups[prefix] = langGroups[prefix] || {};
          langGroups[prefix][lang] = value;
        }
      }
      // Formato con parentesi quadre: prefix[lang]
      else if (field.includes('[') && field.includes(']')) {
        const match = field.match(/^(.+)\[([^\]]+)\]$/);
        if (match) {
          const [, prefix, lang] = match;
          langGroups[prefix] = langGroups[prefix] || {};
          langGroups[prefix][lang] = value;
        }
      }
    }
  });
  return langGroups;
}

/**
 * Builds an index of all .webp files under rootDir for O(1) lookups.
 * @param {string} rootDir - Directory to scan recursively
 * @returns {Promise<Map<string,string>>} - Map from filename to its absolute path
 */
async function indexWebpFiles(rootDir) {
  const map = new Map();
  async function walk(dir) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.isFile() && entry.name.endsWith('.webp')) {
        map.set(entry.name, fullPath);
      }
    }
  }
  await walk(rootDir);
  return map;
}

/**
 * Helper to build a field value, handling special fields and multi-language groups.
 * @param {Object} record - CSV row object
 * @param {string} headerName - Column name in CSV
 * @param {string} key - Internal mapping key
 * @returns {string|Object} - Single string or nested language object
 */
function buildField(record, headerName, key) {
  // Special fields bypass language grouping
  if (SPECIAL_FIELDS.includes(key)) {
    const raw = record[headerName] ?? '';
    logger.info(`[organizeFromCsv] Special field ${key}: "${raw}"`);
    return raw;
  }

  // Determine prefix by stripping [lang] or _lang suffix
  let prefix = headerName.replace(/\[[^\]]+\]$/, '');
  if (prefix.includes('_')) {
    const parts = prefix.split('_');
    if (parts.length >= 2) prefix = parts.slice(0, -1).join('_');
  }

  // Extract all language groups from this record
  const allLang = extractLangValues(record, Object.keys(record));
  const group = allLang[prefix];

  if (group && Object.keys(group).length > 0) {
    logger.info(`[organizeFromCsv] Multi-lang field ${key}: ${JSON.stringify(group)}`);
    return group;
  }

  // Fallback to raw string
  const single = record[headerName] ?? '';
  logger.info(`[organizeFromCsv] Single-lang field ${key}: "${single}"`);
  return single;
}

/**
 * Recursively searches for un file con il nome dato in rootDir.
 * (Maintained for backward compatibility but not used in main flow)
 * @param {string} rootDir
 * @param {string} fileName
 * @returns {Promise<string|null>}
 */
async function findFileRecursive(rootDir, fileName) {
  if (typeof rootDir !== 'string' || typeof fileName !== 'string') {
    throw new TypeError('Invalid arguments to findFileRecursive');
  }
  const entries = await fs.readdir(rootDir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      const found = await findFileRecursive(fullPath, fileName);
      if (found) return found;
    } else if (entry.isFile() && entry.name === fileName) {
      return fullPath;
    }
  }
  return null;
}

/**
 * Reads le intestazioni (prima riga) di un file CSV.
 * @param {string} csvPath
 * @returns {Promise<string[]>}
 */
export async function getCsvHeaders(csvPath) {
  try {
    const content = await fs.readFile(csvPath);
    const records = parse(content, { skip_empty_lines: true });
    return records.length ? records[0] : [];
  } catch (err) {
    logger.error('[organize_by_csv] Error reading CSV headers:', err.message);
    return [];
  }
}

/**
 * Legge una preview di un file CSV con un numero limitato di righe.
 * @param {string} csvPath
 * @param {number} maxRows
 * @returns {Promise<{data: Object[], totalRows: number}>}
 */
export async function getCsvPreview(csvPath, maxRows = 10) {
  try {
    const content = await fs.readFile(csvPath);
    const allRecords = parse(content, { columns: true, skip_empty_lines: true });
    return { data: allRecords.slice(0, maxRows), totalRows: allRecords.length };
  } catch (err) {
    logger.error('[organize_by_csv] Error reading CSV preview:', err.message);
    return { data: [], totalRows: 0 };
  }
}

/**
 * Organizza immagini e miniature e genera metadati JSON per ciascuna cartella documento.
 * Ora supporta colonne CSV con suffisso [lang], producendo oggetti nested.
 * Evita lookup ricorsivi ricorrenti costruendo un indice delle immagini.
 * Consolida la logica di estrazione campo in un helper DRY.
 *
 * @param {string} csvPath - Percorso al file CSV di input
 * @param {string} webpDir - Cartella radice con immagini .webp e sottocartella thumbnails/
 * @param {string} outputDir - Cartella dove scrivere i risultati (organized/, organized_thumbnails/)
 * @param {Function} [progressCallback] - Funzione callback({current,total,file,dest})
 * @param {number|null} [maxLine] - Se specificato, numero massimo di righe da processare
 * @param {{ document: Object, image: Object }} mapping - Mapping nested, key interno → nome colonna CSV
 */
export async function organizeFromCsv(
  csvPath,
  webpDir,
  outputDir,
  progressCallback = () => {},
  maxLine = null,
  mapping = {}
) {
  // 1) Flatten mapping per semplificare l'accesso
  const { document: docMap, image: imgMap } = flattenMapping(mapping);

  // 2) Validazioni input minime
  if (!csvPath || !fsSync.existsSync(csvPath)) {
    return logger.error('[organize_by_csv] Invalid or missing CSV:', csvPath);
  }
  if (!webpDir || !fsSync.existsSync(webpDir)) {
    return logger.error('[organize_by_csv] Invalid or missing webpDir:', webpDir);
  }
  if (!outputDir) {
    return logger.error('[organize_by_csv] Missing outputDir');
  }
  if (!docMap.identifier || !docMap.groupBy) {
    return logger.error('[organize_by_csv] document.identifier and document.groupBy required');
  }

  // 3) Costruisci indice delle immagini per lookup O(1)
  const fileIndex = await indexWebpFiles(webpDir);

  // 4) Lettura e parsing CSV (con colonne come chiavi)
  let records;
  try {
    const content = await fs.readFile(csvPath);
    records = parse(content, { columns: true, skip_empty_lines: true });
  } catch (err) {
    return logger.error('[organize_by_csv] CSV parse error:', err.message);
  }
  if (maxLine != null) {
    const n = Number(maxLine);
    if (!isNaN(n) && n > 0) records = records.slice(0, n);
  }
  logger.info(`[organize_by_csv] ${records.length} records to process`);

  // 5) Prepara cartelle di output
  const organizedDir = path.join(outputDir, 'organized');
  const thumbDir     = path.join(outputDir, 'organized_thumbnails');
  await fs.mkdir(organizedDir, { recursive: true });
  await fs.mkdir(thumbDir,     { recursive: true });

  // 6) Accumulatore metadati
  const folderData = {};
  let current = 0;

  // 7) Loop sui record (possibile parallelizzazione futura)
  for (const row of records) {
    const groupVal = String(row[docMap.groupBy] || '').trim();
    if (!groupVal) continue;

    const folderSlug = slugify(groupVal, { lower: true, strict: true });
    const docFolder = path.join(organizedDir, folderSlug);
    await fs.mkdir(docFolder, { recursive: true });
    await fs.mkdir(path.join(thumbDir, folderSlug), { recursive: true });

    // Inizializza entry metadata se prima volta
    if (!folderData[folderSlug]) {
      const docFields = {};
      for (const [key, headerName] of Object.entries(docMap)) {
        docFields[key] = buildField(row, headerName, key);
      }
      folderData[folderSlug] = { document: docFields, images: [] };
    }

    // Copia immagine principale tramite indice
    const identifier = String(row[docMap.identifier] || '').trim();
    if (!identifier) continue;
    const srcName = `${identifier}.webp`;
    const srcPath = fileIndex.get(srcName);
    if (!srcPath) continue;

    const destName = `${folderSlug}_${identifier}.webp`;
    const destPath = path.join(docFolder, destName);
    await fs.copyFile(srcPath, destPath);

    // Copia miniature (low_quality, gallery) se presenti
    const thumbsRoot = path.join(webpDir, 'thumbnails');
    const rel = path.relative(webpDir, path.dirname(srcPath));
    const thumbSrcDir = path.join(thumbsRoot, rel);
    for (const alias of ['low_quality', 'gallery']) {
      const thumbName = `${identifier}_${alias}.webp`;
      try {
        await fs.copyFile(
          path.join(thumbSrcDir, thumbName),
          path.join(thumbDir, folderSlug, `${folderSlug}_${thumbName}`)
        );
      } catch (err) {
        logger.warn(`[organizeFromCsv] Missing thumbnail ${thumbName}: ${err.code}`);
      }
    }

    // Metadati immagine
    const imgFields = {};
    for (const [key, headerName] of Object.entries(imgMap)) {
      imgFields[key] = buildField(row, headerName, key);
    }
    folderData[folderSlug].images.push(imgFields);

    // Callback di progresso
    current++;
    progressCallback({ current, total: records.length, file: srcName, dest: destPath });
  }

  // 8) Scrive JSON metadata per ogni cartella
  for (const [slug, data] of Object.entries(folderData)) {
    const jsonPath = path.join(organizedDir, slug, 'metadata.json');
    await fs.writeFile(jsonPath, JSON.stringify(data, null, 2));
  }

  logger.info('[organize_by_csv] Organization complete');
}
