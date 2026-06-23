const { app, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { bootEchoShell } = require('./electron-shell');

const SERVER_HOST = '127.0.0.1';
const SERVER_PORT = 18000;
const SERVER_ADDRESS = `${SERVER_HOST}:${SERVER_PORT}`;
const HEALTH_URL = `http://${SERVER_ADDRESS}/health`;
const START_TIMEOUT_MS = Number(process.env.ECHO_BACKEND_START_TIMEOUT_MS || 30000);
const HEALTH_POLL_MS = 500;

let backendProcess = null;
let launcherLogPath = null;

function logLauncher(message, error = null) {
    const line = `[${new Date().toISOString()}] ${message}${error ? ` ${error.stack || error.message || error}` : ''}\n`;
    try {
        if (!launcherLogPath && app) {
            launcherLogPath = path.join(app.getPath('userData'), 'launcher.log');
        }
        if (launcherLogPath) {
            fs.mkdirSync(path.dirname(launcherLogPath), { recursive: true });
            fs.appendFileSync(launcherLogPath, line, 'utf8');
        }
    } catch (_) {
        // Logging must never break startup.
    }
    console.log(line.trimEnd());
}

process.on('uncaughtException', (error) => {
    logLauncher('uncaughtException', error);
});

process.on('unhandledRejection', (reason) => {
    logLauncher('unhandledRejection', reason);
});

function fileExists(filePath) {
    try {
        return fs.existsSync(filePath);
    } catch (error) {
        return false;
    }
}

function resolveBackendRoot() {
    const candidates = [];

    if (process.env.ECHO_BACKEND_ROOT) {
        candidates.push(path.resolve(process.env.ECHO_BACKEND_ROOT));
    }

    if (app.isPackaged) {
        candidates.push(path.join(process.resourcesPath, 'backend'));
    }

    candidates.push(path.resolve(__dirname, '..'));

    const backendRoot = candidates.find((candidate) => fileExists(path.join(candidate, 'api_server.py')));
    if (!backendRoot) {
        throw new Error(`未找到后端入口 api_server.py。已检查：${candidates.join(', ')}`);
    }
    return backendRoot;
}

function resolvePythonCommand() {
    return process.env.ECHO_PYTHON || process.env.PYTHON || 'python';
}

function getDefaultWorkspaceRoot(backendRoot) {
    if (app.isPackaged) {
        return path.join(app.getPath('userData'), '_echo_workspace');
    }
    return path.join(backendRoot, '_echo_workspace');
}

function checkHealth(timeoutMs = 1500) {
    return new Promise((resolve) => {
        const request = http.get(HEALTH_URL, { timeout: timeoutMs }, (response) => {
            response.resume();
            resolve(response.statusCode >= 200 && response.statusCode < 300);
        });

        request.on('timeout', () => {
            request.destroy();
            resolve(false);
        });
        request.on('error', () => resolve(false));
    });
}

async function waitForHealth(timeoutMs) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        if (await checkHealth(HEALTH_POLL_MS)) {
            return true;
        }
        await new Promise((resolve) => setTimeout(resolve, HEALTH_POLL_MS));
    }
    return false;
}

function startBackend(backendRoot) {
    const pythonCommand = resolvePythonCommand();
    const defaultWorkspaceRoot = getDefaultWorkspaceRoot(backendRoot);
    const runtimeConfigFile = path.join(app.getPath('userData'), 'runtime-config.json');
    fs.mkdirSync(defaultWorkspaceRoot, { recursive: true });
    fs.mkdirSync(path.dirname(runtimeConfigFile), { recursive: true });

    const env = {
        ...process.env,
        ECHO_PROJECT_ROOT: backendRoot,
        ECHO_RUNTIME_CONFIG_FILE: runtimeConfigFile,
        ECHO_DEFAULT_WORKSPACE_ROOT: defaultWorkspaceRoot,
        ECHO_RELOAD: '0',
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
    };

    backendProcess = spawn(pythonCommand, ['api_server.py'], {
        cwd: backendRoot,
        env,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
    });

    backendProcess.stdout.on('data', (chunk) => {
        console.log(`[backend] ${chunk.toString().trimEnd()}`);
    });
    backendProcess.stderr.on('data', (chunk) => {
        console.error(`[backend] ${chunk.toString().trimEnd()}`);
    });
    backendProcess.on('exit', (code, signal) => {
        console.log(`[backend] exited code=${code} signal=${signal || ''}`);
        backendProcess = null;
    });
    backendProcess.on('error', (error) => {
        console.error('[backend] failed to start:', error);
    });
}

function stopBackend() {
    if (!backendProcess || backendProcess.killed) {
        return;
    }
    try {
        backendProcess.kill();
    } catch (error) {
        console.error('[backend] failed to stop:', error);
    }
}

async function ensureBackendReady() {
    logLauncher('ensureBackendReady start');
    if (await checkHealth()) {
        logLauncher('backend is already running');
        return;
    }

    const backendRoot = resolveBackendRoot();
    logLauncher(`backendRoot=${backendRoot}`);
    startBackend(backendRoot);

    const ready = await waitForHealth(START_TIMEOUT_MS);
    if (!ready) {
        logLauncher('backend health check timed out');
        dialog.showErrorBox(
            'Echo 后端启动失败',
            `未能在 ${Math.round(START_TIMEOUT_MS / 1000)} 秒内连接到 ${HEALTH_URL}。\n\n` +
            '请确认已安装 Python 依赖，或在 ECHO_PYTHON 中指定 Python 路径。'
        );
    } else {
        logLauncher('backend health check ok');
    }
}

app.whenReady()
    .then(ensureBackendReady)
    .finally(() => {
        logLauncher('bootEchoShell start');
        bootEchoShell({
            mode: 'desktop',
            defaultServerAddress: SERVER_ADDRESS,
            showDevTools: process.env.ECHO_OPEN_DEVTOOLS === '1',
        });
    });

app.on('before-quit', stopBackend);
