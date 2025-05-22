/**
 * Questo file viene caricato come "preload script" nella finestra Electron.
 * Serve a esporre in modo sicuro alcune API di Electron (IPC) al contesto del renderer (frontend),
 * evitando di esporre direttamente Node.js e mantenendo la sicurezza (contextIsolation).
 *
 * In pratica, crea un oggetto globale `window.electronAPI` accessibile dal codice JS della pagina,
 * che permette di:
 *   - Aprire dialog per selezionare cartelle di input/output
 *   - Avviare e fermare il processo di elaborazione immagini
 *   - Ricevere aggiornamenti di progresso (progress bar, CSV, ecc.)
 *   - Verificare la presenza di file CSV in una cartella
 */

const { ipcRenderer, contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Mostra dialog per selezionare la cartella di input
  selectFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  // Mostra dialog per selezionare la cartella di output
  selectOutputFolder: () => ipcRenderer.invoke('dialog:openOutputFolder'),
  // Avvia il processo di elaborazione immagini (parametri: input, output, maxCsvLine, crop)
  processImages: (dir, outputDir = null, maxCsvLine = null, crop = true) => ipcRenderer.invoke('process:images', dir, outputDir, maxCsvLine, crop),
  // Ferma il processo di elaborazione immagini
  stopProcessing: () => ipcRenderer.send('process:stop'),
  // Riceve aggiornamenti di progresso (callback chiamata ad ogni update)
  onProgressUpdate: (callback) => ipcRenderer.on('progress:update', (event, progress) => callback(progress)),
  // Riceve aggiornamenti di progresso per la fase CSV
  onCsvProgress: (callback) => ipcRenderer.on('csv:progress', (event, progress) => callback(progress)),
  // Verifica se nella cartella selezionata è presente un file CSV
  hasCsvInFolder: (dir) => ipcRenderer.invoke('hasCsvInFolder', dir)
});
