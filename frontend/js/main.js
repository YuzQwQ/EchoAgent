(() => {
    const dom = window.dom;
    const appState = window.appState;
    const appEnv = window.appEnv || {};
    const storage = window.storage;
    const runtimeConfig = window.runtimeConfig;
    const updateConnectionBadge = window.updateConnectionBadge;
    const renderHelpers = window.renderHelpers;
    const messageStore = window.messageStore;
    const traceStore = window.traceStore;
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
            getServerAddress: () => appState.connection.serverAddress,
            getAccessToken: () => storage.getAccessToken(),
            getAdminToken: () => storage.getAdminToken(),
            normalizeServerAddress,
            onWs: (socket) => {
                window.runtime?.setWs(socket);
            },
            onConnectedChange: (connected) => {
                window.runtime?.setConnected(connected);
            },
            onStatus: (online, text) => updateConnectionBadge(online, text),
            onSystemMessage: (text) => {
                window.appendSystemMessage?.(text);
            },
            onSendEnabled: (enabled) => {
                if (dom.miniSendBtn) {
                    dom.miniSendBtn.disabled = !enabled;
                }
                if (dom.sendBtn) {
                    dom.sendBtn.disabled = !enabled;
                }
            },
            onUserInput: (content) => {
                messageStore?.addUserMessage(content);
                renderHelpers?.handleUserInput(content);
            },
            onTraceEvent: (event) => {
                traceStore?.addEvent(event);
            },
            onChunkStart: () => {
                messageStore?.startAssistantMessage();
                renderHelpers?.handleChunkStart();
                audioPlayer.reset();
            },
            onChunkText: (text) => {
                messageStore?.appendAssistantChunk(text);
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
                messageStore?.finishAssistantMessage();
                renderHelpers?.handleChunkDone();
            },
            onErrorMessage: (content) => {
                messageStore?.addSystemMessage(content);
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
        getServerAddress: () => appState.connection.serverAddress,
        getRuntimeConfig: () => storage.getRuntimeConfig(),
        hasRuntimeConfig: () => false,
        applyRuntimeConfig: runtimeConfig.applyRuntimeConfig,
        onStatus: (online, text) => updateConnectionBadge(online, text),
        onDone: () => connectWebSocket()
    });
})();
