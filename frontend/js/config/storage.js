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

    const runtimeConfigKey = 'runtime_model_config';
    const runtimeRememberKey = 'runtime_model_remember';
    const adminTokenKey = 'runtime_admin_token';

    const getRuntimeRemember = () => {
        return localStorage.getItem(runtimeRememberKey) === 'true';
    };

    const setRuntimeRemember = (value) => {
        const enabled = !!value;
        localStorage.setItem(runtimeRememberKey, enabled ? 'true' : 'false');
        if (!enabled) {
            localStorage.removeItem(runtimeConfigKey);
        }
    };

    const getRuntimeConfig = () => {
        try {
            const remember = getRuntimeRemember();
            const storage = remember ? localStorage : sessionStorage;
            const raw = storage.getItem(runtimeConfigKey);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            console.warn('Invalid runtime config in browser storage', e);
            return {};
        }
    };

    const setRuntimeConfig = (config, remember) => {
        const shouldRemember = remember !== undefined ? !!remember : getRuntimeRemember();
        setRuntimeRemember(shouldRemember);
        const storage = shouldRemember ? localStorage : sessionStorage;
        storage.setItem(runtimeConfigKey, JSON.stringify(config || {}));
        if (!shouldRemember) {
            localStorage.removeItem(runtimeConfigKey);
        }
    };

    const getAdminToken = () => {
        return sessionStorage.getItem(adminTokenKey) || '';
    };

    const setAdminToken = (value) => {
        const trimmed = (value || '').trim();
        if (trimmed) {
            sessionStorage.setItem(adminTokenKey, trimmed);
        } else {
            sessionStorage.removeItem(adminTokenKey);
        }
    };

    window.storage = {
        getServerIp,
        setServerIp,
        getObserverMode,
        setObserverMode,
        getRuntimeConfig,
        setRuntimeConfig,
        getRuntimeRemember,
        setRuntimeRemember,
        getAdminToken,
        setAdminToken
    };
})();
