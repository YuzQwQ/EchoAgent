const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let apiProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile('index.html');
  
  // 开发模式下打开 DevTools
  // mainWindow.webContents.openDevTools();

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
