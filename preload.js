const { ipcRenderer, contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  processImages: (dir) => ipcRenderer.invoke('process:images', dir),
  stopProcessing: () => ipcRenderer.send('process:stop'),
  onProgressUpdate: (callback) => ipcRenderer.on('progress:update', (event, progress) => callback(progress))
});
