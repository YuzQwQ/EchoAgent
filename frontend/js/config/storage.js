(() => {
    const getServerIp = (fallback) => {
        return localStorage.getItem('server_ip') || fallback || '';
    };

    const setServerIp = (value) => {
        localStorage.setItem('server_ip', value || '');
    };

    const getObserverMode = () => {
        return localStorage.getItem('observer_mode') || 'general';
    };

    const setObserverMode = (value) => {
        localStorage.setItem('observer_mode', value || 'general');
    };

    const getRuntimeConfig = () => {
        try {
            const raw = localStorage.getItem('runtime_model_config');
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            console.warn('Invalid runtime config in localStorage', e);
            return {};
        }
    };

    const setRuntimeConfig = (config) => {
        localStorage.setItem('runtime_model_config', JSON.stringify(config || {}));
    };

    window.storage = {
        getServerIp,
        setServerIp,
        getObserverMode,
        setObserverMode,
        getRuntimeConfig,
        setRuntimeConfig
    };
})();
