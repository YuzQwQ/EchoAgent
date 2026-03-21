(() => {
    const dom = {
        serverAddressInput: document.getElementById('server-address-input'),
        adminTokenInput: document.getElementById('admin-token-input'),
        loadConfigBtn: document.getElementById('load-config-btn'),
        saveConfigBtn: document.getElementById('save-config-btn'),
        statusChip: document.getElementById('admin-status-chip'),
        statusText: document.getElementById('admin-status-text'),
        primaryApiKeyInput: document.getElementById('primary-api-key-input'),
        primaryBaseUrlInput: document.getElementById('primary-base-url-input'),
        primaryModelInput: document.getElementById('primary-model-input'),
        visionApiKeyInput: document.getElementById('vision-api-key-input'),
        visionBaseUrlInput: document.getElementById('vision-base-url-input'),
        visionModelInput: document.getElementById('vision-model-input'),
        primaryApiKeyState: document.getElementById('primary-api-key-state'),
        visionApiKeyState: document.getElementById('vision-api-key-state'),
    };

    const storage = window.storage;
    const runtimeConfig = window.runtimeConfig;

    const defaultAddress = location.protocol.startsWith('http')
        ? location.host
        : (storage.getServerAddress('127.0.0.1:18000') || '127.0.0.1:18000');

    const setStatus = (chipText, bodyText, tone = 'info') => {
        if (dom.statusChip) {
            dom.statusChip.textContent = chipText;
            dom.statusChip.style.background = tone === 'error'
                ? 'rgba(220, 53, 69, 0.18)'
                : tone === 'success'
                    ? 'rgba(54, 179, 126, 0.18)'
                    : 'rgba(96, 122, 188, 0.18)';
        }
        if (dom.statusText) {
            dom.statusText.textContent = bodyText;
            dom.statusText.style.color = tone === 'error' ? '#ffb4bf' : 'rgba(221, 229, 255, 0.72)';
        }
    };

    const setKeyState = (element, isSet) => {
        if (!element) return;
        element.textContent = isSet ? 'API Key 已设置' : 'API Key 未设置';
        element.classList.toggle('ok', !!isSet);
        element.classList.toggle('empty', !isSet);
    };

    const syncAuth = () => {
        storage.setServerAddress(dom.serverAddressInput?.value || '');
        storage.setAdminToken(dom.adminTokenInput?.value || '');
    };

    const loadStatus = async () => {
        syncAuth();
        const serverAddress = dom.serverAddressInput?.value?.trim();
        if (!serverAddress) {
            setStatus('缺少地址', '请先填写服务地址。', 'error');
            return;
        }

        setStatus('读取中', '正在读取当前服务端配置...');
        try {
            const result = await runtimeConfig.fetchRuntimeConfigStatus(serverAddress);
            runtimeConfig.fillInputs(dom, {
                primary_base_url: result?.primary?.base_url || '',
                primary_model_name: result?.primary?.model || '',
                vision_base_url: result?.vision?.base_url || '',
                vision_model_name: result?.vision?.model || '',
            });
            if (dom.primaryApiKeyInput) dom.primaryApiKeyInput.value = '';
            if (dom.visionApiKeyInput) dom.visionApiKeyInput.value = '';
            setKeyState(dom.primaryApiKeyState, !!result?.primary?.api_key_set);
            setKeyState(dom.visionApiKeyState, !!result?.vision?.api_key_set);
            setStatus('已同步', '当前模型配置已从服务端读取。', 'success');
        } catch (err) {
            console.warn(err);
            setStatus('读取失败', `读取配置失败：${err.message}`, 'error');
        }
    };

    const saveConfig = async () => {
        syncAuth();
        const serverAddress = dom.serverAddressInput?.value?.trim();
        if (!serverAddress) {
            setStatus('缺少地址', '请先填写服务地址。', 'error');
            return;
        }

        setStatus('保存中', '正在把配置写入服务端...');
        try {
            const payload = runtimeConfig.collectFromInputs(dom);
            const result = await runtimeConfig.applyRuntimeConfig(serverAddress, payload);
            const changed = Array.isArray(result?.changed) ? result.changed : [];
            setStatus(
                '已保存',
                changed.length > 0 ? `已更新字段：${changed.join(', ')}` : '没有检测到可写入的新值。',
                'success'
            );
            await loadStatus();
        } catch (err) {
            console.warn(err);
            setStatus('保存失败', `写入配置失败：${err.message}`, 'error');
        }
    };

    dom.serverAddressInput.value = defaultAddress;
    dom.adminTokenInput.value = storage.getAdminToken();
    setKeyState(dom.primaryApiKeyState, false);
    setKeyState(dom.visionApiKeyState, false);

    dom.loadConfigBtn?.addEventListener('click', loadStatus);
    dom.saveConfigBtn?.addEventListener('click', saveConfig);

    loadStatus();
})();
