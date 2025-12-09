import fs from 'fs/promises';
import path from 'path';
import EXCLUDED_FOLDERS from './excluded_folders.js';

const excludedSet = new Set(
  EXCLUDED_FOLDERS.map(name => name.toLowerCase())
);

/**
 * Restituisce la lista di tutte le cartelle sotto `rootDir`, esclusi i nomi in EXCLUDED_FOLDERS.
 * Traversal iterativo, senza stat aggiuntivi.
 * Includes protection against circular references and excessively deep paths.
 *
 * @param {string} rootDir - Directory di partenza
 * @param {number} maxDepth - Maximum depth to traverse (default: 50)
 * @param {number} maxPathLength - Maximum path length (default: 3500 chars)
 * @returns {Promise<string[]>} - Array di percorsi assoluti delle cartelle trovate
 */
export async function getAllFolders(rootDir, maxDepth = 50, maxPathLength = 3500) {
  const folders = [];
  const visited = new Set(); // Track visited paths to prevent circular references
  const stack = [{ path: rootDir, depth: 0 }];
  const rootDepth = rootDir.split(path.sep).length;

  while (stack.length) {
    const { path: dir, depth } = stack.pop();

    // Skip if already visited (circular reference protection)
    const realPath = path.resolve(dir);
    if (visited.has(realPath)) {
      continue;
    }
    visited.add(realPath);

    // Skip if path is too long (OS limit protection)
    if (dir.length > maxPathLength) {
      console.warn(`[getAllFolders] Path too long, skipping: ${dir.substring(0, 100)}...`);
      continue;
    }

    // Skip if too deep (infinite recursion protection)
    if (depth > maxDepth) {
      console.warn(`[getAllFolders] Max depth (${maxDepth}) exceeded at: ${dir}`);
      continue;
    }

    folders.push(dir);

    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch (err) {
      // Permessi o altri errori, salta questa cartella
      console.warn(`[getAllFolders] Cannot read directory: ${dir} - ${err.message}`);
      continue;
    }

    for (const entry of entries) {
      if (entry.isDirectory()) {
        const name = entry.name;
        if (!excludedSet.has(name.toLowerCase())) {
          const childPath = path.join(dir, name);
          stack.push({ path: childPath, depth: depth + 1 });
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
