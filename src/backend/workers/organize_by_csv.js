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

// Estensioni immagini supportate (per modalità senza ottimizzazione)
const IMAGE_EXTENSIONS = ['.webp', '.tif', '.tiff', '.jpg', '.jpeg', '.png'];

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
 * Costruisce un indice di tutti i file immagine supportati (chiave = basename, valore = info path/estensione)
 * NOTA: se esistono duplicati con lo stesso basename in cartelle diverse, l'ultimo sovrascrive i precedenti.
 */
async function indexImageFiles(rootDir) {
  const fileIndex = new Map();

  async function scanDirectory(directory) {
    try {
      const entries = await fs.readdir(directory, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(directory, entry.name);

        if (entry.isDirectory()) {
          await scanDirectory(fullPath);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          if (!IMAGE_EXTENSIONS.includes(ext)) continue;

          const base = path.basename(entry.name, ext);
          fileIndex.set(base, {
            path: fullPath,
            ext,
            relativeDir: path.dirname(path.relative(rootDir, fullPath))
          });
        }
      }
    } catch (error) {
      logger.warn(`[indexImageFiles] Cannot scan directory ${directory}: ${error.message}`);
    }
  }

  await scanDirectory(rootDir);
  logger.info(`[indexImageFiles] Indexed ${fileIndex.size} image files from ${rootDir}`);
  if (fileIndex.size > 0 && fileIndex.size <= 5) {
    // Log first few entries for debugging when index is small
    const entries = [...fileIndex.entries()].slice(0, 5);
    logger.info(`[indexImageFiles] Sample entries: ${entries.map(([k, v]) => `${k} -> ${v.path}`).join(', ')}`);
  }
  return fileIndex;
}

/**
 * Checks if a directory contains any image files.
 */
async function directoryHasImages(dir) {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile()) {
        const ext = path.extname(entry.name).toLowerCase();
        if (IMAGE_EXTENSIONS.includes(ext)) {
          return true;
        }
      }
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Removes folders that don't contain any image files.
 * Also removes corresponding thumbnail folders and skips metadata writing for empty folders.
 */
async function pruneEmptyFolders(organizedDir, thumbDir) {
  const prunedFolders = [];

  try {
    const entries = await fs.readdir(organizedDir, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;

      const folderPath = path.join(organizedDir, entry.name);
      const hasImages = await directoryHasImages(folderPath);

      if (!hasImages) {
        // Remove the empty organized folder
        await fs.rm(folderPath, { recursive: true, force: true });
        prunedFolders.push(entry.name);

        // Also remove corresponding thumbnail folder if exists
        const thumbFolderPath = path.join(thumbDir, entry.name);
        try {
          await fs.rm(thumbFolderPath, { recursive: true, force: true });
        } catch {
          // Thumbnail folder may not exist
        }

        logger.info(`[pruneEmptyFolders] Removed empty folder: ${entry.name}`);
      }
    }
  } catch (error) {
    logger.warn(`[pruneEmptyFolders] Error scanning folders: ${error.message}`);
  }

  return prunedFolders;
}

/**
 * Trova un'immagine nella cartella specificata provando tutte le estensioni supportate.
 */
function findImageInDir(dir, identifier) {
  for (const ext of IMAGE_EXTENSIONS) {
    const candidate = path.join(dir, `${identifier}${ext}`);
    if (fsSync.existsSync(candidate)) {
      return {
        path: candidate,
        ext,
        relativeDir: path.dirname(path.relative(dir, candidate))
      };
    }
  }
  return null;
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
 * - Altrimenti usa l'indice globale, con fallback a ricerca diretta in webpDir.
 */
async function copyMainImage({
  fileIndex,
  identifier,
  webpDir,
  destFolder,
  folderSlug,
  originDir // string|null
}) {
  let sourceInfo = originDir
    ? findImageInDir(originDir, identifier)
    : fileIndex.get(identifier);

  // Fallback: if not found in index, try direct search in webpDir root
  if (!sourceInfo && !originDir) {
    sourceInfo = findImageInDir(webpDir, identifier);
    if (sourceInfo) {
      logger.info(`[copyMainImage] Found "${identifier}" via direct search in webpDir`);
    }
  }

  if (!sourceInfo) {
    logger.warn(
      `[copyMainImage] Image not found for identifier "${identifier}"${
        originDir ? ` in origin_folder ${originDir}` : ` (searched index and ${webpDir})`
      }`
    );
    return null;
  }

  const destExt = sourceInfo.ext || path.extname(sourceInfo.path) || '.webp';
  // Clean identifier for output filename: remove leading underscores to avoid double underscores
  const cleanIdentifier = identifier.replace(/^_+/, '');
  const destName = `${folderSlug}_${cleanIdentifier}${destExt}`;
  const destPath = path.join(destFolder, destName);

  try {
    await fs.copyFile(sourceInfo.path, destPath);
    logger.info(`[copyMainImage] Copied: ${path.basename(sourceInfo.path)} → ${destName}`);
    return destPath;
  } catch (error) {
    logger.error(`[copyMainImage] Failed to copy ${path.basename(sourceInfo.path)}: ${error.message}`);
    return null;
  }
}

/**
 * Copia le miniature associate a un'immagine.
 * - Se originDir è valorizzato, calcola le miniature coerentemente al relativo path.
 * - Altrimenti usa la posizione derivata dall'indice, con fallback a ricerca diretta.
 */
async function copyThumbnails({
  webpDir,
  fileIndex,
  identifier,
  thumbDir,
  folderSlug,
  originDir // string|null
}) {
  let sourceInfo = originDir
    ? findImageInDir(originDir, identifier)
    : fileIndex.get(identifier);

  // Fallback: if not found in index, try direct search in webpDir root
  if (!sourceInfo && !originDir) {
    sourceInfo = findImageInDir(webpDir, identifier);
  }

  if (!sourceInfo) {
    logger.warn(`[copyThumbnails] No source image found for ${identifier}, skipping thumbnails`);
    return;
  }

  const thumbnailsRoot = path.join(webpDir, 'thumbnails');
  const relativePath = originDir
    ? path.relative(webpDir, path.dirname(sourceInfo.path))
    : (sourceInfo.relativeDir || path.relative(webpDir, path.dirname(sourceInfo.path)));
  const thumbSourceDir = path.join(thumbnailsRoot, relativePath);
  const thumbDestDir = path.join(thumbDir, folderSlug);

  await fs.mkdir(thumbDestDir, { recursive: true });

  // Clean identifier for output filename: remove leading underscores to avoid double underscores
  const cleanIdentifier = identifier.replace(/^_+/, '');

  for (const type of THUMBNAIL_TYPES) {
    const thumbName = `${identifier}_${type}.webp`;  // Source uses original identifier
    const thumbSource = path.join(thumbSourceDir, thumbName);
    const thumbDest = path.join(thumbDestDir, `${folderSlug}_${cleanIdentifier}_${type}.webp`);  // Dest uses clean identifier

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
  const fileIndex = await indexImageFiles(webpDir);

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
  progressCallback({ current: 0, total: records.length, codice: 'Avvio organizzazione CSV' });

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

  for (let index = 0; index < records.length; index++) {
    const record = records[index];
    const current = index + 1;
    try {
      // Estrai valori chiave
      // Normalize values: remove any file extension if present (common when identifier/groupBy use filename column)
      const extensionRegex = /\.(jpg|jpeg|png|tif|tiff|webp)$/i;
      const rawGroupValue = String(record[documentMapping.groupBy] || '').trim();
      const groupValue = rawGroupValue.replace(extensionRegex, '');
      const rawIdentifier = String(record[documentMapping.identifier] || '').trim();
      const identifier = rawIdentifier.replace(extensionRegex, '');

      if (!groupValue || !identifier) {
        logger.warn(`[organizeFromCsv] Skipping record: missing groupBy(${groupValue}) or identifier(${identifier})`);
        progressCallback({ current, total: records.length, codice: identifier || groupValue || '' });
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
          progressCallback({ current, total: records.length, codice: identifier });
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
        progressCallback({ current, total: records.length, codice: identifier });
      } else {
        // Se origin_folder era presente e l'immagine non è stata copiata, è già stato loggato errore.
        // Se non era presente, abbiamo già avvisato con warn nel copyMainImage.
        progressCallback({ current, total: records.length, codice: identifier });
      }

      processedCount++;
    } catch (error) {
      logger.error(`[organizeFromCsv] Error processing record ${current}: ${error.message}`);
      progressCallback({ current, total: records.length, codice: '' });
    }
  }

  // =============================================================================
  // PRUNE EMPTY FOLDERS
  // =============================================================================

  logger.info('[organizeFromCsv] Pruning empty folders...');
  const prunedFolders = await pruneEmptyFolders(organizedDir, thumbDir);

  // Remove pruned folders from metadata
  for (const folderSlug of prunedFolders) {
    delete folderMetadata[folderSlug];
  }

  if (prunedFolders.length > 0) {
    logger.info(`[organizeFromCsv] Pruned ${prunedFolders.length} empty folders`);
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
    `[organizeFromCsv] Organization complete! Processed ${processedCount} records into ${Object.keys(folderMetadata).length} folders (pruned ${prunedFolders.length} empty)`
  );
}
