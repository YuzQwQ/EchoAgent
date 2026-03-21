(() => {
    const dom = window.dom;
    const storage = window.storage;
    const runtimeConfig = window.runtimeConfig;
    const appState = window.appState;
    const appEnv = window.appEnv || {};
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
            showSubtitle?.(`Me: ${text}`, true);
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
            reader.onload = (e) => {
                const base64Data = e.target.result;
                showSubtitle?.('[Image sent]', true);
                wsClient?.sendImage(base64Data);
            };
            reader.readAsDataURL(file);
        };

        dom.miniInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });

        dom.miniInput.addEventListener('keydown', (e) => {
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
        const updateAdminLink = () => {
            if (!dom.openAdminPanelLink) {
                return;
            }

            const serverAddress = dom.serverIpInput?.value?.trim() || appState.connection.serverAddress;
            if (!serverAddress) {
                dom.openAdminPanelLink.href = '#';
                dom.openAdminPanelLink.setAttribute('aria-disabled', 'true');
                return;
            }

            dom.openAdminPanelLink.href = runtimeConfig.buildAdminUrl(serverAddress);
            dom.openAdminPanelLink.removeAttribute('aria-disabled');
        };

        const openModal = () => {
            dom.serverIpInput.value = appState.connection.serverAddress;
            if (dom.observerModeSelect) dom.observerModeSelect.value = appState.observer.mode;
            if (dom.accessTokenInput) {
                dom.accessTokenInput.value = storage.getAccessToken();
            }
            updateAdminLink();

            if (dom.runtimeConfigStatus) {
                dom.runtimeConfigStatus.textContent = appEnv.isBridge
                    ? 'Bridge mode only stores the server address, observer mode, and access token.'
                    : 'Runtime model configuration has moved to the separate Admin page.';
            }
            dom.settingsModal.style.display = 'block';
        };

        const closeModal = () => {
            dom.settingsModal.style.display = 'none';
        };

        const saveSettings = async () => {
            const newAddress = dom.serverIpInput.value.trim();
            const newMode = dom.observerModeSelect ? dom.observerModeSelect.value : 'general';
            const accessToken = dom.accessTokenInput ? dom.accessTokenInput.value : '';

            if (!newAddress) return;

            const prevAddress = appState.connection.serverAddress;
            storage.setServerAddress(newAddress);
            storage.setObserverMode(newMode);
            storage.setAccessToken(accessToken);
            appState.connection.serverAddress = newAddress;
            appState.observer.mode = newMode;

            if (dom.runtimeConfigStatus) {
                dom.runtimeConfigStatus.textContent = 'Connection settings saved.';
            }

            alert('Settings saved.');
            closeModal();

            if (newAddress !== prevAddress) {
                location.reload();
            }
        };

        dom.serverIpInput?.addEventListener('input', updateAdminLink);
        dom.settingsBtn.addEventListener('click', openModal);
        dom.cancelSettingsBtn?.addEventListener('click', closeModal);
        dom.saveSettingsBtn?.addEventListener('click', saveSettings);
    }

    if (dom?.ttsBtn) {
        let enabled = dom.ttsBtn.classList.contains('active');

        const updateUi = () => {
            dom.ttsBtn.textContent = enabled ? 'ON' : 'OFF';
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
            showSubtitle?.(`[System]: ${text}`, true);
        };

        dom.closeBtn.addEventListener('click', () => {
            if (confirm('Let Echo rest for now?')) {
                window.close();
            }
        });
    }
})();
