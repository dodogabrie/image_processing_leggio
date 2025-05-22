const { app, BrowserWindow } = require('electron');
const { ipcMain, dialog } = require('electron');

const { fork } = require('child_process');
const fs = require('fs').promises;
const { processDir } = require('./src/image_processor');
const { organizeFromCsv } = require('./src/workers/organize_by_csv');

const { setupPythonEnv } = require('./src/scripts/setup-python');

const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 800, height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'src', 'electron', 'preload.js')
    }
  });
  win.loadFile('index.html');
}

ipcMain.handle('dialog:openFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
  if (canceled) return null;
  return filePaths[0];
});

ipcMain.handle('dialog:openOutputFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory', 'createDirectory'] });
  if (canceled) return null;
  return filePaths[0];
});

ipcMain.handle('hasCsvInFolder', async (event, dir) => {
  try {
    const files = await require('fs').promises.readdir(dir);
    return files.some(f => f.toLowerCase().endsWith('.csv'));
  } catch {
    return false;
  }
});

let shouldStop = false;

ipcMain.handle('process:images', async (event, dir, outputDir = null, maxCsvLine = null, crop = true) => {
  const webContents = event.sender;
  shouldStop = false;
  try {
    // Installa/env Python solo se crop è abilitato
    if (crop) {
      try {
        setupPythonEnv();
      } catch (err) {
        console.error('Errore setupPythonEnv:', err);
        dialog.showErrorBox('Errore ambiente Python', `Impossibile creare l'ambiente Python:\n\n${err.message}`);
        return { success: false, error: 'Errore ambiente Python: ' + err.message };
      }
    }

    // Calcola il nome della cartella di input (quella selezionata)
    const inputBaseName = require('path').basename(dir);
    // Se outputDir è fornito, aggiungi inputBaseName come sottocartella
    const finalOutputDir = outputDir
      ? require('path').join(outputDir, inputBaseName)
      : undefined;

    await processDir(
      dir,
      (progress) => { webContents.send('progress:update', progress); },
      undefined,
      finalOutputDir,
      undefined,
      () => shouldStop,
      undefined,
      true,
      crop // pass crop parameter
    );

    // --- STOP CHECK dopo immagini ---
    if (shouldStop) {
      return { success: false, error: 'Processo interrotto dall\'utente.' };
    }

    // Cerca il primo file .csv nella cartella di input
    let csvPath = null;
    try {
      const files = await require('fs').promises.readdir(dir);
      csvPath = files.find(f => f.toLowerCase().endsWith('.csv'));
      if (csvPath) csvPath = require('path').join(dir, csvPath);
    } catch {}
    if (csvPath) {
      // --- STOP CHECK prima di CSV ---
      if (shouldStop) {
        return { success: false, error: 'Processo interrotto dall\'utente.' };
      }
      await organizeFromCsv(
        csvPath,
        finalOutputDir || require('path').join(process.env.HOME || process.env.USERPROFILE, 'output1', inputBaseName),
        finalOutputDir || require('path').join(process.env.HOME || process.env.USERPROFILE, 'output1', inputBaseName),
        (csvProgress) => webContents.send('csv:progress', csvProgress),
        maxCsvLine
      );
    }

    // --- STOP CHECK prima di ZIP ---
    if (shouldStop) {
      return { success: false, error: 'Processo interrotto dall\'utente.' };
    }

    // --- ZIP WORKER CALL ---
    const baseOut = finalOutputDir || path.join(process.env.HOME || process.env.USERPROFILE, 'output1', inputBaseName);
    const organizedDir = path.join(baseOut, 'organized');
    const organizedThumbDir = path.join(baseOut, 'organized_thumbnails');
    const outputZip = path.join(baseOut, 'final_output.zip');

    try {
      await fs.access(organizedDir);
      await fs.access(organizedThumbDir);

      await new Promise((resolve, reject) => {
        if (shouldStop) return reject(new Error('Processo interrotto dall\'utente.'));
        const zipWorkerPath = path.join(__dirname, 'src', 'workers', 'zip_worker.js');
        const child = fork(
          zipWorkerPath,
          [ organizedDir, organizedThumbDir, outputZip ],
          {
            execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
            stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
            // windowsHide: true
          }
        );
        child.on('exit', code => {
          if (code === 0) resolve();
          else reject(new Error(`zip_worker exited with code ${code}`));
        });
      });

      webContents.send('zip:done', outputZip);
    } catch (err) {
      console.error('Errore creazione zip finale:', err.message);
      webContents.send('zip:error', err.message);
      throw new Error('Errore creazione zip finale: ' + err.message);
    }
    // --- END ZIP WORKER CALL ---

    return { success: true };
  } catch (err) {
    console.error('Errore durante l\'elaborazione delle immagini:', err);
    return { success: false, error: err && err.message ? err.message : String(err) };
  }
});

ipcMain.on('process:stop', () => {
  shouldStop = true;
});

app.whenReady().then(() => {
  createWindow();
});


process.on('uncaughtException', (err) => {
  console.error('Uncaught Exception:', err);
});
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection:', reason);
});
