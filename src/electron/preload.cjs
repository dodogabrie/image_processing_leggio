// preload.cjs
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {

  selectFolder: () => ipcRenderer.invoke('dialog:openFolder'),

  selectOutputFolder: () => ipcRenderer.invoke('dialog:openOutputFolder'),

  processImages: (dir, outputDir = null, maxCsvLine = null, crop = true, csvMapping, optimizeVideos = false) =>
    ipcRenderer.invoke('process:images', dir, outputDir, maxCsvLine, crop, csvMapping, optimizeVideos),

  stopProcessing: () => ipcRenderer.send('process:stop'),

  onProgressUpdate: callback =>
    ipcRenderer.on('progress:update', (_e, progress) => callback(progress)),

  onCsvProgress: callback =>
    ipcRenderer.on('csv:progress', (_e, progress) => callback(progress)),

  hasCsvInFolder: dir => ipcRenderer.invoke('hasCsvInFolder', dir),

  readDir: (dir) => ipcRenderer.invoke('fs:readDir', dir),

  getCsvHeaders: (csvPath) => ipcRenderer.invoke('csv:getHeaders', csvPath),

  getCsvPreview: (csvPath, maxRows) => ipcRenderer.invoke('csv:getPreview', csvPath, maxRows),

  readPublicFile: (filename) => ipcRenderer.invoke('public:readFile', filename),

  writePublicFile: (filename, content) => ipcRenderer.invoke('public:writeFile', filename, content),
});
