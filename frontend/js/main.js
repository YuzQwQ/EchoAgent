(() => {
    const dom = window.dom;
    const appState = window.appState;
    const storage = window.storage;
    const runtimeConfig = window.runtimeConfig;
    const updateConnectionBadge = window.updateConnectionBadge;
    const renderHelpers = window.renderHelpers;
    const live2d = window.live2d;
    const audioPlayer = window.audioPlayer;
    const normalizeServerAddress = runtimeConfig.normalizeServerAddress;

    let ws = null;
    let isConnected = false;
    window.runtime = {
        getWs: () => ws,
        isConnected: () => isConnected,
        getTtsEnabled: () => (window.ttsToggle?.isEnabled ? window.ttsToggle.isEnabled() : false),
        setWs: (socket) => {
            ws = socket;
        },
        setConnected: (value) => {
            isConnected = value;
        }
    };

    window.onload = () => {
        live2d.init({
            onError: (message) => window.appendSystemMessage?.(message)
        });
    };

    const wsClient = window.wsClient;

    const connectWebSocket = () => {
        wsClient.connect({
            getServerAddress: () => appState.connection.serverIp,
            normalizeServerAddress,
            onWs: (socket) => {
                window.runtime?.setWs(socket);
            },
            onConnectedChange: (connected) => {
                window.runtime?.setConnected(connected);
            },
            onStatus: (online, text) => updateConnectionBadge(online, text),
            onSystemMessage: (text) => window.appendSystemMessage?.(text),
            onSendEnabled: (enabled) => {
                if (dom.miniSendBtn) {
                    dom.miniSendBtn.disabled = !enabled;
                }
            },
            onUserInput: (content) => {
                renderHelpers?.handleUserInput(content);
            },
            onChunkStart: () => {
                renderHelpers?.handleChunkStart();
                audioPlayer.reset();
            },
            onChunkText: (text) => {
                renderHelpers?.handleChunkText(text);
            },
            onEmotion: (emotion) => {
                live2d.triggerMotion(emotion);
            },
            onAudioStream: (data) => {
                audioPlayer.handleStream(data);
            },
            onAudio: (data) => {
                audioPlayer.queueSingle(data.content);
            },
            onDone: () => {
                renderHelpers?.handleChunkDone();
            },
            onErrorMessage: (content) => {
                renderHelpers?.handleError(content);
            }
        });
    };

    audioPlayer.init({
        onIdle: () => {
            renderHelpers?.handleAudioIdle();
        }
    });

    window.runtimeBootstrap.init({
        getServerAddress: () => appState.connection.serverIp,
        getRuntimeConfig: () => storage.getRuntimeConfig(),
        hasRuntimeConfig: runtimeConfig.hasRuntimeConfig,
        applyRuntimeConfig: runtimeConfig.applyRuntimeConfig,
        onStatus: (online, text) => updateConnectionBadge(online, text),
        onDone: () => connectWebSocket()
    });
})();
