// File: backend/workers/organize_by_csv.js
import fs from 'fs/promises';
import * as fsSync from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import slugify from 'slugify';
import Logger from '../Logger.js';

const logger = new Logger();

// =============================================================================
// CONSTANTS & CONFIGURATION
// =============================================================================

/**
 * Campi trattati come "semplici" (no multi-lingua) in buildFieldValue.
 * Includiamo 'origin_folder' perché è un riferimento di percorso, non un testo multilingua.
 */
const SPECIAL_FIELDS = [
  'identifier', 'origin_folder', 'groupBy', 'active', 'date',
  'language', 'metadata_available', 'metadata_just_year'
];

/**
 * Tipi di miniature che ci aspettiamo accanto alle immagini principali.
 */
const THUMBNAIL_TYPES = ['low_quality', 'gallery'];

// =============================================================================
/**
 * NOTE DI FUNZIONAMENTO SU origin_folder
 *
 * - origin_folder è un valore testuale presente nel CSV (es. "Archivio/FondoX/Set01" o "Set01").
 * - È sempre da intendersi come cartella presente DA QUALCHE PARTE sotto webpDir (potrebbe essere annidata).
 * - Strategia:
 *    1) Provo un match diretto: path.join(webpDir, origin_folder)
 *    2) Se non esiste, cerco ricorsivamente in webpDir una cartella con nome uguale all’ultimo segmento di origin_folder.
 *    3) Se la trovo, cerco lì file "identifier.webp".
 * - Se origin_folder è valorizzato e non trovo il file, il record viene considerato in errore (non fallback all’indice globale).
 * - Se origin_folder NON è valorizzato, uso l’indice globale come in passato.
 */
// =============================================================================

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Appiattisce un mapping nested in chiavi flat (dot-notation) separando le sezioni document/image.
 */
function flattenMapping(mapping) {
  const result = { document: {}, image: {} };

  for (const section of ['document', 'image']) {
    const sectionData = mapping[section] || {};

    for (const [key, value] of Object.entries(sectionData)) {
      if (value != null && typeof value === 'object' && !Array.isArray(value)) {
        // Nested object: flatten con dot notation
        for (const [subKey, subValue] of Object.entries(value)) {
          result[section][`${key}.${subKey}`] = String(subValue ?? '').trim();
        }
      } else {
        // Simple value
        result[section][key] = String(value ?? '').trim();
      }
    }
  }

  return result;
}

/**
 * Costruisce un indice di tutti i file .webp (chiave = nome file, valore = path completo)
 * NOTA: se esistono duplicati con lo stesso nome in cartelle diverse, l'ultimo sovrascrive i precedenti.
 * Questo è accettabile SOLO quando non viene passato origin_folder.
 */
async function indexWebpFiles(rootDir) {
  const fileIndex = new Map();

  async function scanDirectory(directory) {
    try {
      const entries = await fs.readdir(directory, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(directory, entry.name);

        if (entry.isDirectory()) {
          await scanDirectory(fullPath);
        } else if (entry.isFile() && entry.name.endsWith('.webp')) {
          fileIndex.set(entry.name, fullPath);
        }
      }
    } catch (error) {
      logger.warn(`[indexWebpFiles] Cannot scan directory ${directory}: ${error.message}`);
    }
  }

  await scanDirectory(rootDir);
  logger.info(`[indexWebpFiles] Indexed ${fileIndex.size} .webp files`);
  return fileIndex;
}

/**
 * Risolve la cartella di origine sotto webpDir.
 * 1) Prova un match diretto: webpDir / originFolder (che può essere annidato)
 * 2) Se non esiste, cerca ricorsivamente una directory il cui nome sia uguale all’ultimo segmento di originFolder.
 * @param {string} webpDir
 * @param {string} originFolder (es. "Archivio/FondoX/Set01" o "Set01")
 * @returns {Promise<string|null>} path assoluto della cartella se trovata, altrimenti null
 */
async function resolveOriginFolder(webpDir, originFolder) {
  if (!originFolder) return null;

  const directCandidate = path.join(webpDir, originFolder);
  try {
    const stat = await fs.stat(directCandidate);
    if (stat.isDirectory()) {
      return directCandidate;
    }
  } catch {
    // non esiste come path diretto; continuiamo con la ricerca ricorsiva
  }

  // Ricerca ricorsiva per nome dell'ultimo segmento
  const targetName = path.basename(originFolder);
  let found = null;

  async function search(dir) {
    if (found) return; // short-circuit se già trovato

    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const full = path.join(dir, entry.name);

      if (entry.name === targetName) {
        found = full;
        return;
      }
      await search(full);
      if (found) return;
    }
  }

  await search(webpDir);
  return found;
}

// =============================================================================
// MULTI-LANGUAGE SUPPORT
// =============================================================================

/**
 * Estrae e raggruppa valori multi-lingua da un record CSV
 * Supporta:
 *   - prefix_lang (es: title_en, title_it)
 *   - prefix[lang] (es: title[en], title[it])
 */
function extractLanguageGroups(record) {
  const languageGroups = {};

  for (const [fieldName, value] of Object.entries(record)) {
    if (!value || value === '') continue;

    let prefix, language;

    // Formato: prefix_lang (es: title_en, title_it)
    if (fieldName.includes('_')) {
      const parts = fieldName.split('_');
      if (parts.length >= 2) {
        language = parts[parts.length - 1];
        prefix = parts.slice(0, -1).join('_');
      }
    }

    // Formato: prefix[lang] (es: title[en], title[it])
    else if (fieldName.includes('[') && fieldName.includes(']')) {
      const match = fieldName.match(/^(.+)\[([^\]]+)\]$/);
      if (match) {
        prefix = match[1];
        language = match[2];
      }
    }

    if (prefix && language) {
      if (!languageGroups[prefix]) {
        languageGroups[prefix] = {};
      }
      languageGroups[prefix][language] = value;
    }
  }

  return languageGroups;
}

/**
 * Costruisce il valore di un campo, gestendo multi-lingua e campi speciali.
 */
function buildFieldValue(record, csvColumnName, mappingKey) {
  // I campi speciali non supportano multi-lingua
  if (SPECIAL_FIELDS.includes(mappingKey)) {
    return record[csvColumnName] ?? '';
  }

  // Determina il prefisso rimuovendo suffissi di lingua
  let prefix = csvColumnName.replace(/\[[^\]]+\]$/, ''); // Rimuove [lang]
  if (prefix.includes('_')) {
    const parts = prefix.split('_');
    if (parts.length >= 2) {
      prefix = parts.slice(0, -1).join('_');
    }
  }

  // Cerca gruppi di lingua per questo prefisso
  const languageGroups = extractLanguageGroups(record);
  const languageGroup = languageGroups[prefix];

  if (languageGroup && Object.keys(languageGroup).length > 0) {
    return languageGroup; // Restituisce oggetto multi-lingua
  }

  // Fallback a valore singolo
  return record[csvColumnName] ?? '';
}

// =============================================================================
// FILE OPERATIONS
// =============================================================================

/**
 * Copia un file immagine principale nella cartella di destinazione.
 * - Se originDir è valorizzato, cerca SOLO lì.
 * - Altrimenti usa l'indice globale.
 */
async function copyMainImage({
  fileIndex,
  identifier,
  webpDir,
  destFolder,
  folderSlug,
  originDir // string|null
}) {
  const sourceName = `${identifier}.webp`;
  let sourcePath = null;

  if (originDir) {
    const candidate = path.join(originDir, sourceName);
    if (fsSync.existsSync(candidate)) {
      sourcePath = candidate;
    } else {
      logger.error(`[copyMainImage] Image not found in origin_folder: ${candidate}`);
      return null; // secondo i requisiti, se origin_folder è presente ma il file manca → errore per il record
    }
  } else {
    // Fallback al comportamento precedente (indice globale)
    sourcePath = fileIndex.get(sourceName);
    if (!sourcePath) {
      logger.warn(`[copyMainImage] Image not found: ${sourceName}`);
      return null;
    }
  }

  const destName = `${folderSlug}_${identifier}.webp`;
  const destPath = path.join(destFolder, destName);

  try {
    await fs.copyFile(sourcePath, destPath);
    logger.info(`[copyMainImage] Copied: ${sourceName} → ${destName}`);
    return destPath;
  } catch (error) {
    logger.error(`[copyMainImage] Failed to copy ${sourceName}: ${error.message}`);
    return null;
  }
}

/**
 * Copia le miniature associate a un'immagine.
 * - Se originDir è valorizzato, calcola le miniature coerentemente al relativo path.
 * - Altrimenti usa la posizione derivata dall’indice.
 */
async function copyThumbnails({
  webpDir,
  fileIndex,
  identifier,
  thumbDir,
  folderSlug,
  originDir // string|null
}) {
  const sourceName = `${identifier}.webp`;
  let sourcePath = null;

  if (originDir) {
    const candidate = path.join(originDir, sourceName);
    if (!fsSync.existsSync(candidate)) {
      // se manca qui, come sopra, niente thumbnails
      logger.warn(`[copyThumbnails] Main image missing at origin_folder, cannot copy thumbnails: ${candidate}`);
      return;
    }
    sourcePath = candidate;
  } else {
    sourcePath = fileIndex.get(sourceName);
    if (!sourcePath) {
      return; // se non abbiamo neanche la principale, usciamo
    }
  }

  const thumbnailsRoot = path.join(webpDir, 'thumbnails');
  const relativePath = path.relative(webpDir, path.dirname(sourcePath));
  const thumbSourceDir = path.join(thumbnailsRoot, relativePath);
  const thumbDestDir = path.join(thumbDir, folderSlug);

  await fs.mkdir(thumbDestDir, { recursive: true });

  for (const type of THUMBNAIL_TYPES) {
    const thumbName = `${identifier}_${type}.webp`;
    const thumbSource = path.join(thumbSourceDir, thumbName);
    const thumbDest = path.join(thumbDestDir, `${folderSlug}_${thumbName}`);

    try {
      await fs.copyFile(thumbSource, thumbDest);
      logger.info(`[copyThumbnails] Copied thumbnail: ${thumbName}`);
    } catch (error) {
      logger.warn(`[copyThumbnails] Missing thumbnail ${thumbName}: ${error.code}`);
    }
  }
}

/**
 * Costruisce i metadati per un record CSV (document + image) usando il mapping.
 */
function buildMetadata(record, documentMapping, imageMapping) {
  const documentFields = {};
  const imageFields = {};

  // Costruisci campi documento
  for (const [mappingKey, csvColumn] of Object.entries(documentMapping)) {
    documentFields[mappingKey] = buildFieldValue(record, csvColumn, mappingKey);
  }

  // Costruisci campi immagine
  for (const [mappingKey, csvColumn] of Object.entries(imageMapping)) {
    imageFields[mappingKey] = buildFieldValue(record, csvColumn, mappingKey);
  }

  return { documentFields, imageFields };
}

// =============================================================================
// PUBLIC API FUNCTIONS
// =============================================================================

/**
 * Legge le intestazioni di un file CSV (riga 0).
 */
export async function getCsvHeaders(csvPath) {
  try {
    const content = await fs.readFile(csvPath);
    const records = parse(content, { skip_empty_lines: true });
    return records.length > 0 ? records[0] : [];
  } catch (error) {
    logger.error(`[getCsvHeaders] Error reading CSV headers: ${error.message}`);
    return [];
  }
}

/**
 * Legge una preview di un file CSV (prime N righe, con colonne).
 */
export async function getCsvPreview(csvPath, maxRows = 10) {
  try {
    const content = await fs.readFile(csvPath);
    const allRecords = parse(content, { columns: true, skip_empty_lines: true });

    return {
      data: allRecords.slice(0, maxRows),
      totalRows: allRecords.length
    };
  } catch (error) {
    logger.error(`[getCsvPreview] Error reading CSV preview: ${error.message}`);
    return { data: [], totalRows: 0 };
  }
}

/**
 * Funzione principale per organizzare immagini e metadati da un file CSV
 *
 * @param {string} csvPath - Percorso al file CSV
 * @param {string} webpDir - Directory contenente le immagini .webp
 * @param {string} outputDir - Directory di output per i risultati organizzati
 * @param {Function} progressCallback - Callback per aggiornamenti di progresso
 * @param {number|null} maxLine - Numero massimo di righe da processare (null = tutte)
 * @param {Object} mapping - Mapping delle colonne CSV ai campi interni
 */
export async function organizeFromCsv(
  csvPath,
  webpDir,
  outputDir,
  progressCallback = () => {},
  maxLine = null,
  mapping = {}
) {
  logger.info('[organizeFromCsv] Starting CSV organization process');

  // =============================================================================
  // VALIDATION & SETUP
  // =============================================================================

  if (!csvPath || !fsSync.existsSync(csvPath)) {
    throw new Error(`CSV file not found: ${csvPath}`);
  }

  if (!webpDir || !fsSync.existsSync(webpDir)) {
    throw new Error(`WebP directory not found: ${webpDir}`);
  }

  if (!outputDir) {
    throw new Error('Output directory is required');
  }

  // Prepara il mapping
  const { document: documentMapping, image: imageMapping } = flattenMapping(mapping);

  if (!documentMapping.identifier || !documentMapping.groupBy) {
    throw new Error('document.identifier and document.groupBy are required in mapping');
  }

  logger.info(`[organizeFromCsv] Document mapping: ${JSON.stringify(documentMapping)}`);
  logger.info(`[organizeFromCsv] Image mapping: ${JSON.stringify(imageMapping)}`);

  // =============================================================================
  // FILE INDEX & CSV PARSING
  // =============================================================================

  // Costruisci indice delle immagini (usato solo quando origin_folder non è fornito)
  logger.info('[organizeFromCsv] Building file index...');
  const fileIndex = await indexWebpFiles(webpDir);

  // Leggi e parsing del CSV
  logger.info('[organizeFromCsv] Reading CSV file...');
  let records;
  try {
    const content = await fs.readFile(csvPath);
    records = parse(content, { columns: true, skip_empty_lines: true });
  } catch (error) {
    throw new Error(`CSV parsing failed: ${error.message}`);
  }

  // Applica limite righe se specificato
  if (maxLine != null) {
    const limit = Number(maxLine);
    if (!isNaN(limit) && limit > 0) {
      records = records.slice(0, limit);
      logger.info(`[organizeFromCsv] Limited to ${limit} records`);
    }
  }

  logger.info(`[organizeFromCsv] Processing ${records.length} records`);

  // =============================================================================
  // DIRECTORY SETUP
  // =============================================================================

  const organizedDir = path.join(outputDir, 'organized');
  const thumbDir = path.join(outputDir, 'organized_thumbnails');

  await fs.mkdir(organizedDir, { recursive: true });
  await fs.mkdir(thumbDir, { recursive: true });

  // =============================================================================
  // PROCESS RECORDS
  // =============================================================================

  const folderMetadata = {};
  let processedCount = 0;

  for (const record of records) {
    try {
      // Estrai valori chiave
      const groupValue = String(record[documentMapping.groupBy] || '').trim();
      const identifier = String(record[documentMapping.identifier] || '').trim();

      if (!groupValue || !identifier) {
        logger.warn(`[organizeFromCsv] Skipping record: missing groupBy(${groupValue}) or identifier(${identifier})`);
        continue;
      }

      // Leggi eventuale origin_folder dal record (se mappato)
      const originFolderVal =
        documentMapping.origin_folder ? String(record[documentMapping.origin_folder] || '').trim() : '';

      // Risolvi la cartella di origine sotto webpDir (se fornita)
      let originDir = null;
      if (originFolderVal) {
        originDir = await resolveOriginFolder(webpDir, originFolderVal);
        if (!originDir) {
          // Se l'utente ha passato origin_folder ma non la troviamo, segnaliamo e saltiamo il record.
          logger.error(
            `[organizeFromCsv] origin_folder not found under webpDir: "${originFolderVal}" (webpDir="${webpDir}")`
          );
          continue;
        }
      }

      // Crea slug per la cartella
      const folderSlug = slugify(groupValue, { lower: true, strict: true });
      const documentFolder = path.join(organizedDir, folderSlug);

      // Crea cartelle se necessario
      await fs.mkdir(documentFolder, { recursive: true });

      // Inizializza metadati cartella se prima volta
      if (!folderMetadata[folderSlug]) {
        const { documentFields } = buildMetadata(record, documentMapping, imageMapping);
        folderMetadata[folderSlug] = {
          document: documentFields,
          images: []
        };
      }

      // Copia immagine principale
      const mainImagePath = await copyMainImage({
        fileIndex,
        identifier,
        webpDir,
        destFolder: documentFolder,
        folderSlug,
        originDir // se presente, cerca solo lì
      });

      if (mainImagePath) {
        // Copia miniature
        await copyThumbnails({
          webpDir,
          fileIndex,
          identifier,
          thumbDir,
          folderSlug,
          originDir
        });

        // Aggiungi metadati immagine
        const { imageFields } = buildMetadata(record, documentMapping, imageMapping);
        folderMetadata[folderSlug].images.push(imageFields);

        // Callback di progresso
        progressCallback({
          current: processedCount + 1,
          total: records.length,
          file: `${identifier}.webp`,
          dest: mainImagePath
        });
      } else {
        // Se origin_folder era presente e l'immagine non è stata copiata, è già stato loggato errore.
        // Se non era presente, abbiamo già avvisato con warn nel copyMainImage.
      }

      processedCount++;
    } catch (error) {
      logger.error(`[organizeFromCsv] Error processing record ${processedCount}: ${error.message}`);
    }
  }

  // =============================================================================
  // WRITE METADATA FILES
  // =============================================================================

  logger.info('[organizeFromCsv] Writing metadata files...');

  for (const [folderSlug, metadata] of Object.entries(folderMetadata)) {
    const metadataPath = path.join(organizedDir, folderSlug, 'metadata.json');

    try {
      await fs.writeFile(metadataPath, JSON.stringify(metadata, null, 2), 'utf-8');
      logger.info(`[organizeFromCsv] Written metadata: ${folderSlug}/metadata.json`);
    } catch (error) {
      logger.error(`[organizeFromCsv] Failed to write metadata for ${folderSlug}: ${error.message}`);
    }
  }

  logger.info(
    `[organizeFromCsv] Organization complete! Processed ${processedCount} records into ${Object.keys(folderMetadata).length} folders`
  );
}
