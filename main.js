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

ipcMain.handle('process:images', async (event, dir) => {
  const webContents = event.sender;
  await processDir(dir, (progress) => {
    webContents.send('progress:update', progress);
  });
});
app.whenReady().then(createWindow);
