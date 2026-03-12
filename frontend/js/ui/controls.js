(() => {
    const dom = window.dom;
    const storage = window.storage;
    const runtimeConfig = window.runtimeConfig;
    const appState = window.appState;
    const wsClient = window.wsClient;
    const audioPlayer = window.audioPlayer;
    const showSubtitle = window.showSubtitle;

    if (dom?.toggleInputBtn && dom.inputOverlay && dom.miniInput) {
        dom.toggleInputBtn.addEventListener('click', () => {
            if (dom.inputOverlay.style.display === 'flex') {
                dom.inputOverlay.style.display = 'none';
                dom.inputOverlay.classList.remove('show');
            } else {
                dom.inputOverlay.style.display = 'flex';
                dom.inputOverlay.classList.add('show');
                dom.miniInput.focus();
            }
        });
    }

    if (dom?.miniInput && dom.miniSendBtn && dom.imageUpload && dom.imgBtn) {
        const isConnected = () => (window.runtime?.isConnected ? window.runtime.isConnected() : false);

        const sendMessage = () => {
            const text = dom.miniInput.value.trim();
            if (!text || !isConnected()) return;

            audioPlayer?.reset();
            showSubtitle?.(`我: ${text}`, true);
            wsClient?.sendText(text);

            dom.miniInput.value = '';
            if (dom.inputOverlay) {
                dom.inputOverlay.style.display = 'none';
                dom.inputOverlay.classList.remove('show');
            }
        };

        const sendImage = (file) => {
            if (!isConnected()) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                const base64Data = e.target.result;
                showSubtitle?.('📷 [发送了一张图片]', true);
                wsClient?.sendImage(base64Data);
            };
            reader.readAsDataURL(file);
        };

        dom.miniInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });

        dom.miniInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        dom.miniSendBtn.addEventListener('click', sendMessage);
        dom.imgBtn.addEventListener('click', () => dom.imageUpload.click());

        dom.imageUpload.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                sendImage(this.files[0]);
                this.value = '';
            }
        });
    }

    if (dom?.settingsBtn && dom.settingsModal && storage && runtimeConfig && appState) {
        const openModal = () => {
            dom.serverIpInput.value = appState.connection.serverIp;
            if (dom.observerModeSelect) dom.observerModeSelect.value = appState.observer.mode;
            runtimeConfig.fillInputs(dom, storage.getRuntimeConfig());
            if (dom.runtimeConfigStatus) {
                dom.runtimeConfigStatus.textContent = '提示：模型配置仅保存在当前浏览器。';
            }
            dom.settingsModal.style.display = 'block';
        };

        const closeModal = () => {
            dom.settingsModal.style.display = 'none';
        };

        const saveSettings = async () => {
            const newIp = dom.serverIpInput.value.trim();
            const newMode = dom.observerModeSelect ? dom.observerModeSelect.value : 'general';
            const runtime = runtimeConfig.collectFromInputs(dom);

            if (!newIp) return;

            const prevIp = appState.connection.serverIp;
            storage.setServerIp(newIp);
            storage.setObserverMode(newMode);
            storage.setRuntimeConfig(runtime);
            appState.connection.serverIp = newIp;
            appState.observer.mode = newMode;

            if (dom.runtimeConfigStatus) {
                dom.runtimeConfigStatus.textContent = '正在应用模型配置...';
            }
            try {
                const applyResult = await runtimeConfig.applyRuntimeConfig(newIp, runtime);
                if (dom.runtimeConfigStatus) {
                    dom.runtimeConfigStatus.textContent = applyResult?.skipped
                        ? '未填写模型参数，本次仅保存地址与模式。'
                        : '模型配置已下发到后端并生效。';
                }
            } catch (err) {
                console.warn(err);
                if (dom.runtimeConfigStatus) {
                    dom.runtimeConfigStatus.textContent = `模型配置下发失败：${err.message}`;
                }
            }

            alert('设置已保存。');
            closeModal();

            if (newIp !== prevIp) {
                location.reload();
            }
        };

        dom.settingsBtn.addEventListener('click', openModal);
        dom.cancelSettingsBtn?.addEventListener('click', closeModal);
        dom.saveSettingsBtn?.addEventListener('click', saveSettings);
    }

    if (dom?.ttsBtn) {
        let enabled = dom.ttsBtn.classList.contains('active');

        const updateUi = () => {
            dom.ttsBtn.textContent = enabled ? '🔊' : '🔇';
            dom.ttsBtn.classList.toggle('active', enabled);
        };

        const setEnabled = (value) => {
            enabled = !!value;
            updateUi();
        };

        const toggle = () => {
            setEnabled(!enabled);
        };

        dom.ttsBtn.addEventListener('click', toggle);
        updateUi();

        window.ttsToggle = {
            isEnabled: () => enabled,
            setEnabled,
            toggle
        };
    }

    if (dom?.closeBtn) {
        window.appendSystemMessage = (text) => {
            showSubtitle?.(`[系统]: ${text}`, true);
        };

        dom.closeBtn.addEventListener('click', () => {
            if (confirm('确定要让 Echo 休息一下吗？')) {
                window.close();
            }
        });
    }
})();
