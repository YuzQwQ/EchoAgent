(() => {
    const params = new URLSearchParams(window.location.search || '');
    const mode = (params.get('mode') || 'desktop').trim().toLowerCase() || 'desktop';
    const defaultServerAddress = (params.get('server') || '').trim();

    window.appEnv = {
        mode,
        isBridge: mode === 'bridge',
        defaultServerAddress,
    };
})();
