const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// 屏蔽 Electron 安全警告（仅用于开发环境）
process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true';

let mainWindow;
let apiProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 350,  // 瘦身：只展示人物
    height: 600,
    frame: false,       // 无边框
    transparent: true,  // 透明背景
    alwaysOnTop: true,  // 置顶
    hasShadow: false,   // 去掉系统阴影
    resizable: true,    // 允许调整大小
    skipTaskbar: false, // 任务栏可见（方便找回，也可以设为true隐藏）
    fullscreenable: false, // 禁止全屏 (防止 F11 误触导致无法操作)
    maximizable: false,    // 禁止最大化
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    }
  });

  // 移除默认菜单 (也会禁用 F11 等快捷键)
  mainWindow.setMenu(null);

  mainWindow.loadFile('index.html');
  
  // 开发模式下打开 DevTools (调试时取消注释)
  mainWindow.webContents.openDevTools({ mode: 'detach' });

  // [新增] 监听渲染进程的截屏请求
  const { ipcMain, desktopCapturer } = require('electron');

  ipcMain.handle('get-screen-source-id', async () => {
    try {
        const sources = await desktopCapturer.getSources({ types: ['screen'] });
        // 获取主屏幕 (通常是第一个)
        const source = sources[0];
        return source.id;
    } catch (error) {
        console.error('Failed to get screen sources:', error);
        return null;
    }
  });

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function startApiServer() {
  // 启动 Python FastAPI 服务
  // 假设在开发环境，直接调用 python api_server.py
  // 生产环境需要调用打包好的 exe
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const apiPath = path.join(__dirname, '../api_server.py');
  
  console.log(`Starting API Server: ${pythonCmd} ${apiPath}`);
  
  apiProcess = spawn(pythonCmd, [apiPath], {
    cwd: path.join(__dirname, '..'), // 设置工作目录为项目根目录，以便读取 .env
    shell: true
  });

  apiProcess.stdout.on('data', (data) => {
    console.log(`API stdout: ${data}`);
  });

  apiProcess.stderr.on('data', (data) => {
    console.error(`API stderr: ${data}`);
  });
  
  apiProcess.on('close', (code) => {
    console.log(`API process exited with code ${code}`);
  });
}

app.whenReady().then(() => {
  // startApiServer(); // 暂时手动启动 API 服务以便调试，稳定后再自动启动
  createWindow();

  app.on('activate', function () {
    if (mainWindow === null) createWindow();
  });
});

app.on('window-all-closed', function () {
  // 杀死 Python 进程
  if (apiProcess) {
    apiProcess.kill();
  }
  
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
    if (apiProcess) {
        apiProcess.kill();
    }
});
