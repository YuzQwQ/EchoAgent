(() => {
    let ipcRenderer = null;
    try {
        if (typeof require === 'function') {
            const electron = require('electron');
            ipcRenderer = electron && electron.ipcRenderer ? electron.ipcRenderer : null;
        }
    } catch (e) {
        ipcRenderer = null;
    }
    window.electronBridge = {
        ipcRenderer,
        isElectronEnv: !!ipcRenderer
    };
})();
