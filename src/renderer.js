let selectedFolder = null;
let selectedOutput = null;
let processing = false;

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

async function selectOutput() {
  const folder = await window.electronAPI.selectOutputFolder();
  if (folder) {
    selectedOutput = folder;
    document.getElementById('selectedOutput').textContent = `Output: ${folder}`;
  }
}

async function start() {
  if (selectedFolder) {
    processing = true;
    document.getElementById('progressText').textContent = '';
    document.getElementById('progressBar').value = 0;
    document.getElementById('loader').style.display = 'block';
    document.getElementById('stopButton').disabled = false;
    document.getElementById('processButton').disabled = true;
    const crop = document.getElementById('cropCheckbox').checked; // Fixed the method call
    const maxCsvLine = parseInt(document.getElementById('maxCsvLine').value) || null;
    try {
      document.getElementById('progressText').textContent = 'Inizio elaborazione...';
      const result = await window.electronAPI.processImages(selectedFolder, selectedOutput, maxCsvLine, crop); // Updated method call
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

function stop() {
  if (processing) {
    window.electronAPI.stopProcessing();
    document.getElementById('stopButton').disabled = true;
  }
}

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

window.electronAPI.onCsvProgress((progress) => {
  const { current, total, codice, src, dest } = progress;
  let text = `Organizzazione CSV: ${current} di ${total}`;
  if (codice) {
    text += `\nUltimo: ${codice}`;
  }
  document.getElementById('csvProgressText').textContent = text;
});

