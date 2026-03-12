const { app, BrowserWindow, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// 屏蔽 Electron 安全警告（仅用于开发环境）
process.env['ELECTRON_DISABLE_SECURITY_WARNINGS'] = 'true';

// [Critical] 允许 HTTP 非安全源使用 getUserMedia (摄像头/麦克风/屏幕共享)
// 必须在 app 'ready' 事件之前调用
app.commandLine.appendSwitch('unsafely-treat-insecure-origin-as-secure', 'http://192.168.0.19:8000');

let mainWindow;
let apiProcess;
let mousePollInterval;

function startGlobalMousePolling() {
    if (mousePollInterval) clearInterval(mousePollInterval);
    
    // 每 30ms (约 30fps) 轮询一次鼠标位置
    mousePollInterval = setInterval(() => {
        if (!mainWindow || mainWindow.isDestroyed()) return;

        try {
            const point = screen.getCursorScreenPoint();
            const bounds = mainWindow.getBounds();
            
            // 计算相对于窗口左上角的坐标
            const relativeX = point.x - bounds.x;
            const relativeY = point.y - bounds.y;
            
            // 发送给渲染进程 (同时发送全局坐标，用于全屏追踪)
            mainWindow.webContents.send('global-mouse-move', { 
                x: relativeX, 
                y: relativeY,
                globalX: point.x,
                globalY: point.y
            });
        } catch (e) {
            // ignore
        }
    }, 30);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 380,  // 调整为更紧凑的宽度
    height: 600, // 调整为更紧凑的高度
    frame: false,       // 无边框
    transparent: true,  // 透明背景
    alwaysOnTop: true,  // 置顶
    type: 'toolbar',    // [Fix] 尝试提高窗口层级
    hasShadow: false,   // 去掉系统阴影
    resizable: true,    // 允许调整大小
    skipTaskbar: false, // 任务栏可见（方便找回，也可以设为true隐藏）
    fullscreenable: false, // 禁止全屏 (防止 F11 误触导致无法操作)
    maximizable: false,    // 禁止最大化
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
      backgroundThrottling: false // [Critical] 防止窗口失去焦点/鼠标移出时页面被冻结
    }
  });

  // [Fix] 强制设置置顶级别为 'screen-saver' (Windows上最高层级，可覆盖全屏任务栏)
  mainWindow.setAlwaysOnTop(true, 'screen-saver');

  // 移除默认菜单 (也会禁用 F11 等快捷键)
  mainWindow.setMenu(null);

  mainWindow.loadFile('index.html');
  
  // 开发模式下打开 DevTools (调试时取消注释)
  mainWindow.webContents.openDevTools({ mode: 'detach' });
  
  // 启动鼠标轮询
  startGlobalMousePolling();

  // [新增] 监听渲染进程的截屏请求
  const { ipcMain, desktopCapturer } = require('electron');

  // 动作列表窗口引用
  let motionWindow = null;

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

  // 打开动作列表窗口
  ipcMain.on('open-motion-window', (event, motions) => {
    if (motionWindow) {
        motionWindow.focus();
        // 如果窗口已存在，更新数据
        motionWindow.webContents.send('init-motions', motions);
        return;
    }

    motionWindow = new BrowserWindow({
        width: 400,
        height: 600,
        title: '动作控制器',
        autoHideMenuBar: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    motionWindow.loadFile('motion.html');

    motionWindow.webContents.on('did-finish-load', () => {
        motionWindow.webContents.send('init-motions', motions);
    });

    motionWindow.on('closed', () => {
        motionWindow = null;
    });
  });

  // 转发动作指令: MotionWindow -> MainWindow
  ipcMain.on('trigger-motion', (event, data) => {
      if (mainWindow) {
          mainWindow.webContents.send('play-motion', data);
      }
  });

  mainWindow.on('closed', function () {
    mainWindow = null;
    if (mousePollInterval) clearInterval(mousePollInterval); // 停止轮询
    // 主窗口关闭时，也关闭动作窗口
    if (motionWindow) {
        motionWindow.close();
    }
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
