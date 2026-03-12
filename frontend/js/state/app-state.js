(() => {
    let defaultAddress = '127.0.0.1:18000';
    if (location.protocol.startsWith('http')) {
        defaultAddress = location.host;
    }

    const appState = {
        connection: {
            serverIp: window.storage ? window.storage.getServerIp(defaultAddress) : defaultAddress
        },
        observer: {
            mode: window.storage ? window.storage.getObserverMode() : 'general'
        }
    };

    window.appState = appState;
})();
