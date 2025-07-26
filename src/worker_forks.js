/**
 * worker_forks.js
 *
 * Questo modulo fornisce funzioni per lanciare worker esterni (processi figli)
 * per le operazioni di image processing: crop, conversione e generazione thumbnails.
 * Ogni funzione restituisce una Promise che si risolve quando il worker termina.
 */

const path = require('path');
const { fork, spawn } = require('child_process');

/**
 * Esegue il crop di una pagina tramite uno script Python (crop.py).
 * @param {string} input - Percorso file immagine di input
 * @param {string} output - Percorso file immagine di output
 * @param {number} minArea - Area minima (opzionale, default 200000)
 * @returns {Promise<boolean>} - true se crop riuscito, false se no crop, errore se fallisce
 */
function cropPageWorker(input, output, minArea = 200000) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, 'scripts', 'crop.py');

  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, [ scriptPath, input, output, String(minArea) ], {
      stdio: ['ignore','pipe','pipe']
    });
    // Stampa stdout/stderr del processo figlio sulla console principale
    child.stdout.on('data', d => process.stdout.write(d));
    child.stderr.on('data', d => process.stderr.write(d));
    child.on('exit', code => {
      if (code === 0) return resolve(true);   // Crop riuscito
      if (code === 2) return resolve(false);  // Crop non necessario
      reject(new Error(`crop.py exited with code ${code}`));
    });
  });
}

/**
 * Converte un'immagine in webp tramite un worker Node.js (webp_worker.js).
 * @param {string} input - Percorso file di input
 * @param {string} output - Percorso file di output
 * @param {number} retries - Numero di tentativi in caso di errore (default 1)
 * @returns {Promise<void>}
 */
function convertWorker(input, output, retries = 1) {
  return new Promise((resolve, reject) => {
    const child = fork(
      path.join(__dirname, 'workers', 'webp_worker.js'),
      [ input, output ],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore','pipe','pipe','ipc'],
        windowsHide: true
      }
    );
    // Stampa stdout/stderr del worker sulla console principale
    child.stdout.on('data', d => process.stdout.write(d.toString()));
    child.stderr.on('data', d => process.stderr.write(d.toString()));
    child.on('exit', code => {
      if (code === 0) return resolve(); // Conversione riuscita
      if (retries > 0) return resolve(convertWorker(input, output, retries - 1)); // Retry
      reject(new Error(`worker exited with code ${code}`));
    });
  });
}

/**
 * Crea una thumbnail tramite un worker Node.js (thumbnail_worker.js).
 * @param {string} input - Percorso file di input
 * @param {string} output - Percorso file di output
 * @param {string} alias - Stringa JSON con le opzioni di resize/qualità
 * @returns {Promise<void>}
 */
function createThumbnailWorker(input, output, alias) {
  return new Promise((resolve, reject) => {
    const child = fork(
      path.join(__dirname, 'workers', 'thumbnail_worker.js'),
      [ input, output, alias ],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore','pipe','pipe','ipc'],
        windowsHide: true
      }
    );
    // Stampa stdout/stderr del worker sulla console principale
    child.stdout.on('data', d => process.stdout.write(d.toString()));
    child.stderr.on('data', d => process.stderr.write(d.toString()));
    child.on('exit', code => {
      if (code === 0) return resolve(); // Thumbnail creata con successo
      reject(new Error(`thumbnail_worker exited with code ${code}`));
    });
  });
}

module.exports = {
  cropPageWorker,
  convertWorker,
  createThumbnailWorker
};
