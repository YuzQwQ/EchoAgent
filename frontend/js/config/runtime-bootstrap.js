(() => {
    const init = async ({ getServerAddress, getRuntimeConfig, hasRuntimeConfig, applyRuntimeConfig, onStatus, onDone } = {}) => {
        if (typeof onStatus === 'function') {
            onStatus(false, 'Echo 连接中...');
        }
        try {
            const savedConfig = typeof getRuntimeConfig === 'function' ? getRuntimeConfig() : {};
            const hasAnyConfig = typeof hasRuntimeConfig === 'function' ? hasRuntimeConfig(savedConfig) : false;
            if (hasAnyConfig && typeof applyRuntimeConfig === 'function') {
                await applyRuntimeConfig(getServerAddress ? getServerAddress() : '', savedConfig);
                console.log('Runtime model config applied from browser storage.');
            }
        } catch (err) {
            console.warn('Runtime model config apply failed on startup:', err);
        } finally {
            if (typeof onDone === 'function') onDone();
        }
    };

    window.runtimeBootstrap = { init };
})();
