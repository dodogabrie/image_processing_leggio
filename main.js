const { app, BrowserWindow } = require('electron');
const { ipcMain, dialog } = require('electron');

const { processDir } = require('./image_processor');

const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 800, height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  win.loadFile('index.html');
}

ipcMain.handle('dialog:openFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
  if (canceled) return null;
  return filePaths[0];
});

let shouldStop = false;

ipcMain.handle('process:images', async (event, dir) => {
  const webContents = event.sender;
  shouldStop = false;
  try {
    await processDir(dir, (progress) => {
      webContents.send('progress:update', progress);
    }, undefined, undefined, undefined, () => shouldStop);
    return true;
  } catch (err) {
    console.error('Errore durante l\'elaborazione delle immagini:', err);
    return false;
  }
});

ipcMain.on('process:stop', () => {
  shouldStop = true;
});

app.whenReady().then(createWindow);

process.on('uncaughtException', (err) => {
  console.error('Uncaught Exception:', err);
});
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection:', reason);
});
