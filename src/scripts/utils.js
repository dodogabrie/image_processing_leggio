const fs = require('fs').promises;
const path = require('path');
const EXCLUDED_FOLDERS = require('./excluded_folders'); // <-- aggiungi questa riga

/**
 * Restituisce ricorsivamente la lista di tutte le cartelle (inclusa quella di partenza)
 * a partire da 'dir'. Esclude le cartelle presenti in EXCLUDED_FOLDERS.
 * @param {string} dir - Directory di partenza
 * @returns {Promise<string[]>} - Array di percorsi assoluti delle cartelle trovate
 */
async function getAllFolders(dir) {
  let folders = [dir]; // Inizia includendo la cartella di partenza
  const files = await fs.readdir(dir); // Leggi tutti i file/cartelle nella dir corrente
  for (const file of files) {
    const fullPath = path.join(dir, file); // Percorso assoluto dell'elemento
    let stat;
    try {
      stat = await fs.stat(fullPath); // Ottieni info su file/cartella
    } catch {
      continue; // Se errore (es: permessi), salta
    }
    // Escludi le cartelle presenti in EXCLUDED_FOLDERS (case-insensitive)
    if (stat.isDirectory() && !EXCLUDED_FOLDERS.some(ex => ex.toLowerCase() === file.toLowerCase())) {
      folders = folders.concat(await getAllFolders(fullPath));
    }
  }
  return folders; // Ritorna tutte le cartelle trovate (inclusa quella di partenza)
}

module.exports = { getAllFolders };
