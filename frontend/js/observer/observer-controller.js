(() => {
    const dom = window.dom;
    const appState = window.appState;
    const showSubtitle = window.showSubtitle;
    const electronBridge = window.electronBridge;
    if (!dom?.observerBtn) return;

    const ipcRenderer = electronBridge ? electronBridge.ipcRenderer : null;
    const isElectronEnv = !!ipcRenderer;

    let isObserverActive = false;

    const getRuntime = () => window.runtime || {};
    const getWs = () => (getRuntime().getWs ? getRuntime().getWs() : null);
    const getIsConnected = () => (getRuntime().isConnected ? getRuntime().isConnected() : false);

    const startObserverLoop = () => {
        window.observerCapture?.init({ ipcRenderer, getIsConnected })
            .then(() => {
                window.observerAnalyzer?.start({ onSend: sendObserverFrame });
            })
            .catch((e) => {
                console.error('Screen capture failed:', e);
                showSubtitle?.('截图失败: ' + e.message, 3000);
                isObserverActive = false;
                dom.observerBtn.classList.remove('active');
                stopObserverLoop();
            });
    };

    const stopObserverLoop = () => {
        window.observerAnalyzer?.stop();
        window.observerCapture?.stop();
    };

    const sendObserverFrame = ({ dataUrl, eventType }) => {
        const ws = getWs();
        if (!getIsConnected() || !ws || ws.readyState !== 1 || !dataUrl) return false;
        ws.send(JSON.stringify({
            type: 'image',
            content: dataUrl,
            mode: 'observer',
            game_context: {
                name: appState.observer.mode === 'terraria' ? 'Terraria' : 'General'
            }
        }));
        return true;
    };

    dom.observerBtn.addEventListener('click', () => {
        if (!isElectronEnv) {
            showSubtitle?.('浏览器模式暂不支持观察模式，请使用桌面版。', 3000);
            return;
        }
        isObserverActive = !isObserverActive;
        if (isObserverActive) {
            dom.observerBtn.classList.add('active');
            startObserverLoop();
            showSubtitle?.('Echo 正在观察你的屏幕...', 3000);
        } else {
            dom.observerBtn.classList.remove('active');
            stopObserverLoop();
            showSubtitle?.('观察模式已关闭', 3000);
        }
    });
})();
