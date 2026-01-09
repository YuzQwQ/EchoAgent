const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // 可以在这里暴露一些系统级 API，比如剪贴板、文件选择等
});
