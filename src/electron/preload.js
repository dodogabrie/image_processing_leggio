const { ipcRenderer, contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  selectOutputFolder: () => ipcRenderer.invoke('dialog:openOutputFolder'),
  processImages: (dir, testOnly = false, outputDir = null, maxCsvLine = null) => ipcRenderer.invoke('process:images', dir, testOnly, outputDir, maxCsvLine),
  stopProcessing: () => ipcRenderer.send('process:stop'),
  onProgressUpdate: (callback) => ipcRenderer.on('progress:update', (event, progress) => callback(progress)),
  onCsvProgress: (callback) => ipcRenderer.on('csv:progress', (event, progress) => callback(progress)),
  hasCsvInFolder: (dir) => ipcRenderer.invoke('hasCsvInFolder', dir)
});
