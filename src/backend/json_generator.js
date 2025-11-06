// File: backend/json_generator.js
import fs from 'fs/promises';
import * as fsSync from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import slugify from 'slugify';
import Logger from './Logger.js';

import { extractMultiLanguageField } from './scripts/utils.js';

const logger = new Logger();

/**
 * Legge un CSV e restituisce un array di record ({ header: value }).
 * @param {string} csvPath - Percorso del file CSV.
 * @returns {Array<Object>} - Array di oggetti che rappresentano le righe.
 * @throws Error se il CSV non può essere letto o parsato.
 */
async function readCsv(csvPath) {
  if (!csvPath || !fsSync.existsSync(csvPath)) {
    throw new Error(`CSV non trovato: ${csvPath}`);
  }
  const content = await fs.readFile(csvPath, 'utf-8');
  return parse(content, { columns: true, skip_empty_lines: true });
}

/**
 * Genera file JSON a livello di documento per ogni sottocartella organizzata.
 * Ogni folder diventa un "documento" con metadata e array di immagini.
 * @param {string} organizedDir - Directory base con sottocartelle organizzate.
 * @param {string} csvPath - Percorso del CSV sorgente.
 * @param {Object} mapping - Mappa dei campi CSV per documento e immagine, ad esempio:
 *   {
 *     document: {
 *       identifier: 'Codice',
 *       title: 'TITOLO PER LEGGIO\nda compilare Letizia',
 *       creator: 'AUTORE SCATTO\n(se da indicare)\nda compilare Letizia',
 *       active: 'MOSTRARE NEL LEGGIO\nda compilare o revisionare Letizia',
 *       tags: 'CATEGORIA IN PROGRESS\nda controllare Letizia per verificare associazione',
 *       date: 'DATA\nda compilare Letizia',
 *       document_type: 'Materiale',
 *       periodo: 'PERIODO'
 *     },
 *     image: {
 *       nomenclature: 'Soggetto',
 *       rich_description_prefix: 'DIDASCALIA PER LEGGIO',
 *       sequence_number: valueOrFunction,
 *     }
 *   }
 * @returns {Promise<void>}
 */
export async function generateDocumentJson(organizedDir, csvPath, mapping) {
  // Validazioni
  if (!mapping || !mapping.document || !mapping.image) {
    throw new Error('Mapping incompleto: servono mapping.document e mapping.image');
  }

  // 1. Leggi e pulisci CSV
  let records;
  try {
    records = await readCsv(csvPath);
  } catch (err) {
    logger.error('[json_generator] Errore lettura CSV:', err.message);
    throw err;
  }

  // Mappa CSV per rapido lookup: key = codice (filename)
  const docMap = new Map();
  for (const row of records) {
    // Estrai valori document-level
    const docFields = {};
    for (const [key, col] of Object.entries(mapping.document)) {
      let raw = row[col] != null ? String(row[col]).trim() : '';
      if (raw.toLowerCase() === 'nan' || raw === '') raw = null;
      if (key === 'active') {
        docFields.active = raw === 'SÌ' || raw === 'SI' || raw === 'true';
      } else {
        docFields[key] = raw;
      }
    }
    // Identificatore slug basato sul title
    const id = slugify(docFields.title || '', { lower: true, strict: true, locale: 'it' });
    docFields.identifier = id;
    docFields.language = 'it';
    docFields.metadata_available = true;
    docFields.metadata_just_year = false;

    // Estrai info archivio
    const archiveInfo = {
      path: docFields.archive_path || null,
      name: docFields.archive_name || null,
      parent: docFields.parent_archive || null,
      description: extractMultiLanguageField(row, mapping.document.archive_description_prefix)
    };
    docFields.archive = archiveInfo;

    docMap.set(String(row[mapping.document.identifier] || '').trim(), docFields);
  }

  // 2. Genera JSON per ogni cartella
  const subdirs = await fs.readdir(organizedDir, { withFileTypes: true });
  for (const entry of subdirs) {
    if (!entry.isDirectory()) continue;
    const folderName = entry.name;
    const folderPath = path.join(organizedDir, folderName);
    const files = await fs.readdir(folderPath);

    // Documento base
    const docFields = Array.from(docMap.values()).find(d => d.identifier === folderName);
    if (!docFields) {
      logger.warn(`[json_generator] Nessun record CSV corrisponde a folder: ${folderName}`);
      continue;
    }
    const images = [];

    // Processa immagini nella cartella
    for (const file of files) {
      const ext = path.extname(file).toLowerCase();
      if (!['.jpg', '.jpeg', '.png', '.webp'].includes(ext)) continue;
      const basename = path.basename(file, ext);
      const seq = mapping.image.sequence_number || '1';
      // Estrarre eventuale rich_description da colonna CSV
      const richCol = Object.keys(records[0]).find(c => c.trim().toUpperCase().startsWith(mapping.image.rich_description_prefix.toUpperCase()));
      const rich = richCol ? records.find(r => String(r[mapping.document.identifier]).trim() === basename)?.[richCol] : '';

      images.push({
        sequence_number: seq,
        nomenclature: records.find(r => String(r[mapping.document.identifier]).trim() === basename)?.[mapping.image.nomenclature] || '',
        usage: 'master',
        file_href: file,
        code: basename,
        md5: '',
        filesize: '',
        image_dimensions: { length: '', width: '' },
        image_metrics: {
          sampling_frequency_unit: '',
          sampling_frequency_plane: '',
          x_sampling_frequency: '',
          y_sampling_frequency: '',
          photometric_interpretation: '',
          bit_per_sample: ''
        },
        format: { name: ext.replace('.', '').toUpperCase(), mime: `image/${ext.replace('.', '')}`, compression: 'lossy' },
        datetime_created: docFields.date,
        rich_description: rich || '',
        active: docFields.active
      });
    }

    // Assemble documento completo
    const document = { ...docFields, images };
    const jsonPath = path.join(folderPath, `${folderName}.json`);
    try {
      await fs.writeFile(jsonPath, JSON.stringify(document, null, 2), 'utf-8');
      logger.info(`[json_generator] Documento JSON generato: ${jsonPath}`);
    } catch (err) {
      logger.error(`[json_generator] Errore scrittura JSON ${jsonPath}:`, err.message);
    }
  }
}
