// preload.cjs
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {

  selectFolder: () => ipcRenderer.invoke('dialog:openFolder'),

  selectOutputFolder: () => ipcRenderer.invoke('dialog:openOutputFolder'),

  processImages: (dir, outputDir = null, maxCsvLine = null, crop = true, csvMapping, optimizeVideos = false, optimizeImages = true, previewMode = false, aggressivity = 'standard') =>
    ipcRenderer.invoke('process:images', dir, outputDir, maxCsvLine, crop, csvMapping, optimizeVideos, optimizeImages, previewMode, aggressivity),

  stopProcessing: () => ipcRenderer.send('process:stop'),

  cleanupPreview: (outputDir) => ipcRenderer.invoke('cleanup:preview', outputDir),

  onProgressUpdate: callback =>
    ipcRenderer.on('progress:update', (_e, progress) => callback(progress)),

  onCsvProgress: callback =>
    ipcRenderer.on('csv:progress', (_e, progress) => callback(progress)),

  hasCsvInFolder: dir => ipcRenderer.invoke('hasCsvInFolder', dir),

  readDir: (dir) => ipcRenderer.invoke('fs:readDir', dir),

  readThumbnailAsDataUrl: (filePath) => ipcRenderer.invoke('fs:readThumbnailAsDataUrl', filePath),
  readImageAsDataUrl: (filePath) => ipcRenderer.invoke('fs:readImageAsDataUrl', filePath),
  listEntriesDetailed: (dir, organizedRoot, thumbnailsRoot) => ipcRenderer.invoke('fs:listEntriesDetailed', dir, organizedRoot, thumbnailsRoot),
  findOriginalMatch: (processedPath, originalRoot) => ipcRenderer.invoke('fs:findOriginalMatch', processedPath, originalRoot),
  readJsonFile: (filePath) => ipcRenderer.invoke('fs:readJsonFile', filePath),

  getCsvHeaders: (csvPath) => ipcRenderer.invoke('csv:getHeaders', csvPath),

  getCsvPreview: (csvPath, maxRows) => ipcRenderer.invoke('csv:getPreview', csvPath, maxRows),

  readPublicFile: (filename) => ipcRenderer.invoke('public:readFile', filename),

  writePublicFile: (filename, content) => ipcRenderer.invoke('public:writeFile', filename, content),

  deletePublicFile: (filename) => ipcRenderer.invoke('public:deleteFile', filename),

  openExternal: (url) => ipcRenderer.invoke('public:openExternal', url),

  // Log file operations
  getLogContent: () => ipcRenderer.invoke('log:getContent'),
  getLogPath: () => ipcRenderer.invoke('log:getPath'),
  saveLogAs: () => ipcRenderer.invoke('log:saveAs')

});
