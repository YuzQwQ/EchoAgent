(() => {
    const LOCAL_HOSTS = new Set(['127.0.0.1', '0.0.0.0', 'localhost']);

    const isPrivateIpv4 = (host) => {
        const match = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/.exec(host || '');
        if (!match) {
            return false;
        }
        const first = Number(match[1]);
        const second = Number(match[2]);
        if (first === 10 || first === 127) return true;
        if (first === 192 && second === 168) return true;
        if (first === 172 && second >= 16 && second <= 31) return true;
        return false;
    };

    const inferHttpProtocol = (host) => {
        if (LOCAL_HOSTS.has((host || '').toLowerCase()) || isPrivateIpv4(host)) {
            return 'http';
        }
        return 'https';
    };

    const normalizeServerAddress = (value) => {
        const raw = (value || '').trim();
        if (!raw) {
            return {
                raw: '',
                host: '127.0.0.1',
                port: 18000,
                origin: 'http://127.0.0.1:18000',
                baseUrl: 'http://127.0.0.1:18000',
                wsOrigin: 'ws://127.0.0.1:18000',
                wsBaseUrl: 'ws://127.0.0.1:18000',
                httpProtocol: 'http',
                wsProtocol: 'ws'
            };
        }

        let candidate = raw.replace(/^wss?:\/\//i, (match) => (
            match.toLowerCase().startsWith('wss') ? 'https://' : 'http://'
        ));
        if (!/^[a-z]+:\/\//i.test(candidate)) {
            const hostPart = candidate.split('/')[0].split(':')[0];
            candidate = `${inferHttpProtocol(hostPart)}://${candidate}`;
        }

        let parsedUrl;
        try {
            parsedUrl = new URL(candidate);
        } catch (e) {
            parsedUrl = new URL('http://127.0.0.1:18000');
        }

        const httpProtocol = parsedUrl.protocol === 'https:' ? 'https' : 'http';
        const wsProtocol = httpProtocol === 'https' ? 'wss' : 'ws';
        const pathname = parsedUrl.pathname && parsedUrl.pathname !== '/'
            ? parsedUrl.pathname.replace(/\/+$/, '')
            : '';
        const port = parsedUrl.port
            ? Number(parsedUrl.port)
            : httpProtocol === 'https'
                ? 443
                : 80;
        const origin = `${httpProtocol}://${parsedUrl.host}`;
        const wsOrigin = `${wsProtocol}://${parsedUrl.host}`;

        return {
            raw,
            host: parsedUrl.hostname || '127.0.0.1',
            port,
            origin,
            baseUrl: `${origin}${pathname}`,
            wsOrigin,
            wsBaseUrl: `${wsOrigin}${pathname}`,
            httpProtocol,
            wsProtocol
        };
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

    const buildAdminUrl = (serverAddress) => {
        const normalized = normalizeServerAddress(serverAddress);
        return `${normalized.baseUrl}/ui/admin.html`;
    };

    const fetchRuntimeConfigStatus = async (serverAddress) => {
        const normalized = normalizeServerAddress(serverAddress);
        const url = `${normalized.baseUrl}/runtime-config`;
        const headers = {};
        const accessToken = window.storage?.getAccessToken ? window.storage.getAccessToken() : '';
        if (accessToken) {
            headers['X-Access-Token'] = accessToken;
        }
        const adminToken = window.storage?.getAdminToken ? window.storage.getAdminToken() : '';
        if (adminToken) {
            headers['X-Admin-Token'] = adminToken;
        }

        const response = await fetch(url, { headers });
        if (!response.ok) {
            throw new Error(`读取配置失败: HTTP ${response.status}`);
        }
        return await response.json();
    };

    const applyRuntimeConfig = async (serverAddress, runtimeConfig) => {
        const normalized = normalizeServerAddress(serverAddress);
        const url = `${normalized.baseUrl}/runtime-config`;
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
        const accessToken = window.storage?.getAccessToken ? window.storage.getAccessToken() : '';
        if (accessToken) {
            headers['X-Access-Token'] = accessToken;
        }
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
        buildAdminUrl,
        collectFromInputs,
        fillInputs,
        hasRuntimeConfig,
        fetchRuntimeConfigStatus,
        applyRuntimeConfig
    };
})();
