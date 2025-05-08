const { ipcRenderer, contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  selectOutputFolder: () => ipcRenderer.invoke('dialog:openOutputFolder'),
  processImages: (dir, outputDir = null, maxCsvLine = null, crop = true) => ipcRenderer.invoke('process:images', dir, outputDir, maxCsvLine, crop),
  stopProcessing: () => ipcRenderer.send('process:stop'),
  onProgressUpdate: (callback) => ipcRenderer.on('progress:update', (event, progress) => callback(progress)),
  onCsvProgress: (callback) => ipcRenderer.on('csv:progress', (event, progress) => callback(progress)),
  hasCsvInFolder: (dir) => ipcRenderer.invoke('hasCsvInFolder', dir)
});
