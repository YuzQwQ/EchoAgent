const { app, BrowserWindow, screen, ipcMain, desktopCapturer, dialog } = require('electron');

let mainWindow = null;
let motionWindow = null;
let mousePollInterval = null;
let ipcHandlersInstalled = false;

function startGlobalMousePolling() {
    if (mousePollInterval) {
        clearInterval(mousePollInterval);
    }

    mousePollInterval = setInterval(() => {
        if (!mainWindow || mainWindow.isDestroyed()) {
            return;
        }

        try {
            const point = screen.getCursorScreenPoint();
            const bounds = mainWindow.getBounds();
            mainWindow.webContents.send('global-mouse-move', {
                x: point.x - bounds.x,
                y: point.y - bounds.y,
                globalX: point.x,
                globalY: point.y,
            });
        } catch (e) {
            // Ignore transient window state errors.
        }
    }, 30);
}

function stopGlobalMousePolling() {
    if (mousePollInterval) {
        clearInterval(mousePollInterval);
        mousePollInterval = null;
    }
}

function installIpcHandlers() {
    if (ipcHandlersInstalled) {
        return;
    }
    ipcHandlersInstalled = true;

    ipcMain.handle('get-screen-source-id', async () => {
        try {
            const sources = await desktopCapturer.getSources({ types: ['screen'] });
            const source = sources[0];
            return source ? source.id : null;
        } catch (error) {
            console.error('Failed to get screen sources:', error);
            return null;
        }
    });

    ipcMain.handle('select-workspace-directory', async () => {
        try {
            const result = await dialog.showOpenDialog(mainWindow || undefined, {
                title: '选择工作目录',
                properties: ['openDirectory', 'createDirectory'],
            });
            if (result.canceled) {
                return null;
            }
            return result.filePaths?.[0] || null;
        } catch (error) {
            console.error('Failed to select workspace directory:', error);
            return null;
        }
    });

    ipcMain.on('open-motion-window', (event, motions) => {
        if (motionWindow && !motionWindow.isDestroyed()) {
            motionWindow.focus();
            motionWindow.webContents.send('init-motions', motions);
            return;
        }

        motionWindow = new BrowserWindow({
            width: 400,
            height: 600,
            title: 'Echo Motion',
            autoHideMenuBar: true,
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
            },
        });

        motionWindow.loadFile('motion.html');
        motionWindow.webContents.on('did-finish-load', () => {
            motionWindow.webContents.send('init-motions', motions);
        });
        motionWindow.on('closed', () => {
            motionWindow = null;
        });
    });

    ipcMain.on('trigger-motion', (event, data) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('play-motion', data);
        }
    });
}

function createWindow({ mode = 'desktop', defaultServerAddress = '', showDevTools = false } = {}) {
    mainWindow = new BrowserWindow({
        width: 380,
        height: 600,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        type: 'toolbar',
        hasShadow: false,
        resizable: true,
        skipTaskbar: false,
        fullscreenable: false,
        maximizable: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            webSecurity: false,
            backgroundThrottling: false,
        },
    });

    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.setMenu(null);
    mainWindow.loadFile('index.html', {
        query: {
            mode,
            server: defaultServerAddress || '',
        },
    });

    if (showDevTools) {
        mainWindow.webContents.openDevTools({ mode: 'detach' });
    }

    startGlobalMousePolling();

    mainWindow.on('closed', () => {
        mainWindow = null;
        stopGlobalMousePolling();
        if (motionWindow && !motionWindow.isDestroyed()) {
            motionWindow.close();
        }
    });
}

function bootEchoShell({ mode = 'desktop', defaultServerAddress = '', showDevTools = false } = {}) {
    process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true';
    installIpcHandlers();

    app.whenReady().then(() => {
        createWindow({ mode, defaultServerAddress, showDevTools });

        app.on('activate', () => {
            if (mainWindow === null) {
                createWindow({ mode, defaultServerAddress, showDevTools });
            }
        });
    });

    app.on('window-all-closed', () => {
        if (process.platform !== 'darwin') {
            app.quit();
        }
    });
}

module.exports = {
    bootEchoShell,
};
