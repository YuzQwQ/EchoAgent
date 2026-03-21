(() => {
    const appEnv = window.appEnv || {};
    let defaultAddress = appEnv.defaultServerAddress || '';
    if (!defaultAddress && location.protocol.startsWith('http')) {
        defaultAddress = location.host;
    }
    if (!defaultAddress) {
        defaultAddress = appEnv.isBridge ? '' : '127.0.0.1:18000';
    }

    const appState = {
        connection: {
            serverAddress: window.storage ? window.storage.getServerAddress(defaultAddress) : defaultAddress
        },
        observer: {
            mode: window.storage ? window.storage.getObserverMode() : 'general'
        }
    };

    window.appState = appState;
})();
