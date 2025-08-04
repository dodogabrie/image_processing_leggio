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
