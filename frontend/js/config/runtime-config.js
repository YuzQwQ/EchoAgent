(() => {
    const normalizeServerAddress = (value) => {
        const raw = (value || '').trim();
        if (!raw) {
            return { host: '127.0.0.1', port: 18000 };
        }
        let v = raw.replace(/^https?:\/\//i, '').replace(/^wss?:\/\//i, '');
        v = v.replace(/\s+/g, ':');
        v = v.split('/')[0];
        let host = v;
        let port = 18000;
        if (v.includes(':')) {
            const parts = v.split(':');
            host = parts[0] || '127.0.0.1';
            const parsed = Number(parts[1]);
            port = Number.isFinite(parsed) && parsed > 0 ? parsed : 18000;
        } else {
            const ipv4WithPort = v.match(/^(\d+\.\d+\.\d+\.\d+)(\d{2,5})$/);
            if (ipv4WithPort) {
                host = ipv4WithPort[1];
                const parsed = Number(ipv4WithPort[2]);
                port = Number.isFinite(parsed) && parsed > 0 ? parsed : 18000;
            }
        }
        return { host: host || '127.0.0.1', port };
    };

    const collectFromInputs = (dom) => {
        return {
            primary_api_key: dom.primaryApiKeyInput?.value || '',
            primary_base_url: dom.primaryBaseUrlInput?.value || '',
            primary_model_name: dom.primaryModelInput?.value || '',
            vision_api_key: dom.visionApiKeyInput?.value || '',
            vision_base_url: dom.visionBaseUrlInput?.value || '',
            vision_model_name: dom.visionModelInput?.value || ''
        };
    };

    const fillInputs = (dom, config) => {
        const cfg = config || {};
        if (dom.primaryApiKeyInput) dom.primaryApiKeyInput.value = cfg.primary_api_key || '';
        if (dom.primaryBaseUrlInput) dom.primaryBaseUrlInput.value = cfg.primary_base_url || '';
        if (dom.primaryModelInput) dom.primaryModelInput.value = cfg.primary_model_name || '';
        if (dom.visionApiKeyInput) dom.visionApiKeyInput.value = cfg.vision_api_key || '';
        if (dom.visionBaseUrlInput) dom.visionBaseUrlInput.value = cfg.vision_base_url || '';
        if (dom.visionModelInput) dom.visionModelInput.value = cfg.vision_model_name || '';
    };

    const hasRuntimeConfig = (config) => {
        return Object.values(config || {}).some(v => (v || '').trim());
    };

    const applyRuntimeConfig = async (serverAddress, runtimeConfig) => {
        const { host, port } = normalizeServerAddress(serverAddress);
        const httpProtocol = location.protocol === 'https:' ? 'https' : 'http';
        const url = `${httpProtocol}://${host}:${port}/runtime-config`;
        const payload = {};
        const mappings = [
            ['primary_api_key', runtimeConfig.primary_api_key],
            ['primary_base_url', runtimeConfig.primary_base_url],
            ['primary_model_name', runtimeConfig.primary_model_name],
            ['vision_api_key', runtimeConfig.vision_api_key],
            ['vision_base_url', runtimeConfig.vision_base_url],
            ['vision_model_name', runtimeConfig.vision_model_name]
        ];
        for (const [key, value] of mappings) {
            const cleaned = (value || '').trim();
            if (cleaned) {
                payload[key] = cleaned;
            }
        }

        if (Object.keys(payload).length === 0) {
            return { skipped: true };
        }

        const headers = { 'Content-Type': 'application/json' };
        const adminToken = window.storage?.getAdminToken ? window.storage.getAdminToken() : '';
        if (adminToken) {
            headers['X-Admin-Token'] = adminToken;
        }
        const response = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`配置下发失败: HTTP ${response.status}`);
        }
        return await response.json();
    };

    window.runtimeConfig = {
        normalizeServerAddress,
        collectFromInputs,
        fillInputs,
        hasRuntimeConfig,
        applyRuntimeConfig
    };
})();
