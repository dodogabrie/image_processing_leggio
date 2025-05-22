/**
 * renderer.js
 *
 * Questo file contiene tutta la logica JavaScript che viene eseguita nel contesto del renderer (frontend)
 * della tua app Electron. Si occupa di gestire l'interfaccia utente, le interazioni con i pulsanti,
 * la comunicazione con il backend tramite le API esposte dal preload script (window.electronAPI),
 * e l'aggiornamento della UI in base allo stato del processo.
 */

// Variabili globali per tracciare lo stato della selezione e del processo
let selectedFolder = null;   // Cartella di input selezionata
let selectedOutput = null;   // Cartella di output selezionata
let processing = false;      // Flag che indica se è in corso un'elaborazione

/**
 * Funzione chiamata quando l'utente clicca su "Seleziona cartella".
 * Mostra il dialog di selezione, aggiorna la UI e verifica la presenza di un CSV.
 */
async function select() {
  const folder = await window.electronAPI.selectFolder();
  if (folder) {
    selectedFolder = folder;
    document.getElementById('selectedFolder').textContent = `Cartella selezionata: ${folder}`;
    document.getElementById('processButton').disabled = false;
    // --- CSV detection ---
    // Chiedi al backend se c'è un csv nella cartella selezionata
    const hasCsv = await window.electronAPI.hasCsvInFolder(folder);
    document.getElementById('maxCsvLineLabel').style.display = hasCsv ? 'block' : 'none';
  }
}

/**
 * Funzione chiamata quando l'utente clicca su "Seleziona cartella output".
 * Mostra il dialog di selezione e aggiorna la UI.
 */
async function selectOutput() {
  const folder = await window.electronAPI.selectOutputFolder();
  if (folder) {
    selectedOutput = folder;
    document.getElementById('selectedOutput').textContent = `Output: ${folder}`;
  }
}

/**
 * Funzione chiamata quando l'utente clicca su "Processa".
 * Avvia il processo di elaborazione immagini tramite l'API esposta dal preload.
 * Gestisce la UI durante il processo e mostra eventuali errori.
 */
async function start() {
  if (selectedFolder) {
    processing = true;
    document.getElementById('progressText').textContent = '';
    document.getElementById('progressBar').value = 0;
    document.getElementById('loader').style.display = 'block';
    document.getElementById('stopButton').disabled = false;
    document.getElementById('processButton').disabled = true;
    const crop = document.getElementById('cropCheckbox').checked;
    const maxCsvLine = parseInt(document.getElementById('maxCsvLine').value) || null;
    try {
      document.getElementById('progressText').textContent = 'Inizio elaborazione...';
      // Chiede al backend di avviare il processo
      const result = await window.electronAPI.processImages(selectedFolder, selectedOutput, maxCsvLine, crop);
      document.getElementById('progressText').textContent = 'Elaborazione completata.';
      document.getElementById('loader').style.display = 'none';
      document.getElementById('stopButton').disabled = true;
      document.getElementById('processButton').disabled = false;
      processing = false;
      if (result && result.success) {
        alert('Finito!');
      } else if (result && result.error) {
        alert('Errore: ' + result.error);
      } else {
        alert('Errore sconosciuto durante il processo.');
      }
    } catch (err) {
      document.getElementById('loader').style.display = 'none';
      document.getElementById('stopButton').disabled = true;
      document.getElementById('processButton').disabled = false;
      document.getElementById('progressText').textContent = 'Contattare l\'amministrazione.';
      processing = false;
      alert('Errore JS: ' + (err && err.message ? err.message : err));
    }
  }
}

/**
 * Funzione chiamata quando l'utente clicca su "Ferma".
 * Invia un segnale al backend per interrompere il processo.
 */
function stop() {
  if (processing) {
    window.electronAPI.stopProcessing();
    document.getElementById('stopButton').disabled = true;
  }
}

/**
 * Callback che aggiorna la barra di progresso e i testi di stato
 * ogni volta che il backend invia un aggiornamento di progresso.
 */
window.electronAPI.onProgressUpdate((progress) => {
  document.getElementById('loader').style.display = 'none';
  const { current, total, folderIdx, folderTotal, currentFolder, currentFile } = progress;
  let percent = 0;
  if (typeof current === 'number' && typeof total === 'number' && total > 0) {
    percent = Math.floor((current / total) * 100);
    // Aggiorna la barra di Bootstrap
    const bar = document.getElementById('progressBar');
    bar.style.width = percent + '%';
    bar.setAttribute('aria-valuenow', percent);
    bar.textContent = percent + '%';
  }
  let text = '';
  if (folderIdx && folderTotal && currentFolder) {
    text += `Cartella ${folderIdx} di ${folderTotal}: ${currentFolder}\n`;
  }
  if (typeof current === 'number' && typeof total === 'number' && currentFile) {
    text += `File ${current} di ${total}: ${currentFile}`;
  }
  document.getElementById('progressText').textContent = text;
});

/**
 * Callback che aggiorna la UI per la fase di organizzazione CSV.
 */
window.electronAPI.onCsvProgress((progress) => {
  const { current, total, codice, src, dest } = progress;
  let text = `Organizzazione CSV: ${current} di ${total}`;
  if (codice) {
    text += `\nUltimo: ${codice}`;
  }
  document.getElementById('csvProgressText').textContent = text;
});

