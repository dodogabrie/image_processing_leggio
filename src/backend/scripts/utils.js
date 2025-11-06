import fs from 'fs/promises';
import path from 'path';
import EXCLUDED_FOLDERS from './excluded_folders.js';

const excludedSet = new Set(
  EXCLUDED_FOLDERS.map(name => name.toLowerCase())
);

/**
 * Restituisce la lista di tutte le cartelle sotto `rootDir`, esclusi i nomi in EXCLUDED_FOLDERS.
 * Traversal iterativo, senza stat aggiuntivi.
 *
 * @param {string} rootDir - Directory di partenza
 * @returns {Promise<string[]>} - Array di percorsi assoluti delle cartelle trovate
 */
export async function getAllFolders(rootDir) {
  const folders = [];
  const stack = [rootDir];

  while (stack.length) {
    const dir = stack.pop();
    folders.push(dir);

    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      // Permessi o altri errori, salta questa cartella
      continue;
    }

    for (const entry of entries) {
      if (entry.isDirectory()) {
        const name = entry.name;
        if (!excludedSet.has(name.toLowerCase())) {
          stack.push(path.join(dir, name));
        }
      }
    }
  }

  return folders;
}

/**
 * Extracts multi-language fields from a CSV record based on a prefix.
 * @param {Object} record - The CSV record (row).
 * @param {string} prefix - The prefix for the multi-language columns (e.g., 'archive_description').
 * @returns {Object} - An object with language codes as keys and the field values as values.
 */
export function extractMultiLanguageField(record, prefix) {
  const multiLanguageFields = {};
  if (!prefix) {
    return multiLanguageFields;
  }
  for (const [key, value] of Object.entries(record)) {
    if (key.toLowerCase().startsWith(prefix.toLowerCase())) {
      const lang = key.substring(prefix.length).replace(/^_/, '');
      if (lang && value) {
        multiLanguageFields[lang.toLowerCase()] = value;
      }
    }
  }
  return multiLanguageFields;
}
