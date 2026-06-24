const { app, BrowserWindow, screen, ipcMain, desktopCapturer, dialog } = require('electron');

let mainWindow = null;
let motionWindow = null;
let traceWindow = null;
let dailyBoundsBeforeWorkbench = null;
let mousePollInterval = null;
let ipcHandlersInstalled = false;

const SHELL_SIZES = {
    daily: { width: 380, height: 600 },
    workbench: { width: 960, height: 720 },
};

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

    ipcMain.handle('set-shell-mode', async (event, mode) => {
        if (!mainWindow || mainWindow.isDestroyed()) {
            return false;
        }
        const size = SHELL_SIZES[mode] || SHELL_SIZES.daily;
        if (mode === 'workbench') {
            if (!dailyBoundsBeforeWorkbench) {
                dailyBoundsBeforeWorkbench = mainWindow.getBounds();
            }
            mainWindow.setAlwaysOnTop(false);
            mainWindow.setSize(size.width, size.height, true);
            return true;
        }
        if (mode === 'daily') {
            if (dailyBoundsBeforeWorkbench) {
                mainWindow.setBounds(dailyBoundsBeforeWorkbench, true);
                dailyBoundsBeforeWorkbench = null;
            } else {
                mainWindow.setSize(SHELL_SIZES.daily.width, SHELL_SIZES.daily.height, true);
            }
            mainWindow.setAlwaysOnTop(true, 'screen-saver');
            return true;
        }
        mainWindow.setSize(size.width, size.height, true);
        return true;
    });

    ipcMain.handle('open-trace-window', async () => {
        if (traceWindow && !traceWindow.isDestroyed()) {
            traceWindow.focus();
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('trace-window-ready');
            }
            return true;
        }

        traceWindow = new BrowserWindow({
            width: 760,
            height: 520,
            minWidth: 520,
            minHeight: 320,
            title: 'Echo Trace Log',
            autoHideMenuBar: true,
            resizable: true,
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
            },
        });

        traceWindow.loadFile('trace-window.html');
        traceWindow.webContents.on('did-finish-load', () => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('trace-window-ready');
            }
        });
        traceWindow.on('closed', () => {
            traceWindow = null;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('trace-window-closed');
            }
        });
        return true;
    });

    ipcMain.on('trace-window-update', (event, payload) => {
        if (traceWindow && !traceWindow.isDestroyed()) {
            traceWindow.webContents.send('trace-events', payload || {});
        }
    });

    ipcMain.on('trace-window-ready', () => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('trace-window-ready');
        }
    });

    ipcMain.on('trace-window-clear-request', () => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('trace-window-clear-request');
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
        width: SHELL_SIZES.daily.width,
        height: SHELL_SIZES.daily.height,
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
        if (traceWindow && !traceWindow.isDestroyed()) {
            traceWindow.close();
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
