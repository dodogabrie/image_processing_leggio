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

const SPECIAL_FIELDS = [
  'identifier', 'groupBy', 'active', 'date', 
  'language', 'metadata_available', 'metadata_just_year'
];

const THUMBNAIL_TYPES = ['low_quality', 'gallery'];

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Appiattisce un mapping nested in chiavi flat
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
 * Costruisce un indice di tutti i file .webp per lookup veloce
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

// =============================================================================
// MULTI-LANGUAGE SUPPORT
// =============================================================================

/**
 * Estrae e raggruppa valori multi-lingua da un record CSV
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
 * Costruisce il valore di un campo, gestendo multi-lingua e campi speciali
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
 * Copia un file immagine principale nella cartella di destinazione
 */
async function copyMainImage(fileIndex, identifier, sourceDir, destFolder, folderSlug) {
  const sourceName = `${identifier}.webp`;
  const sourcePath = fileIndex.get(sourceName);
  
  if (!sourcePath) {
    logger.warn(`[copyMainImage] Image not found: ${sourceName}`);
    return null;
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
 * Copia le miniature associate a un'immagine
 */
async function copyThumbnails(webpDir, fileIndex, identifier, thumbDir, folderSlug) {
  const sourceName = `${identifier}.webp`;
  const sourcePath = fileIndex.get(sourceName);
  
  if (!sourcePath) return;
  
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
 * Costruisce i metadati per un record CSV
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
 * Legge le intestazioni di un file CSV
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
 * Legge una preview di un file CSV
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
  
  // Valida input
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
  
  // Costruisci indice delle immagini
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
      const mainImagePath = await copyMainImage(
        fileIndex, 
        identifier, 
        webpDir, 
        documentFolder, 
        folderSlug
      );
      
      if (mainImagePath) {
        // Copia miniature
        await copyThumbnails(webpDir, fileIndex, identifier, thumbDir, folderSlug);
        
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
  
  logger.info(`[organizeFromCsv] Organization complete! Processed ${processedCount} records into ${Object.keys(folderMetadata).length} folders`);
}
