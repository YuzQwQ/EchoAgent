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
        let modalOpen = false;

        const setStatus = (message, isError = false) => {
            if (!dom.runtimeConfigStatus) {
                return;
            }
            dom.runtimeConfigStatus.textContent = message || '';
            dom.runtimeConfigStatus.classList.toggle('is-error', !!isError);
        };

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

        const selectWorkspaceDirectory = async () => {
            try {
                const electron = window.require?.('electron');
                if (!electron?.ipcRenderer) {
                    return null;
                }
                return await electron.ipcRenderer.invoke('select-workspace-directory');
            } catch (error) {
                console.warn('Workspace directory picker failed:', error);
                return null;
            }
        };

        const loadWorkspaceRoot = async () => {
            if (!dom.workspaceRootInput) {
                return;
            }
            try {
                const status = await runtimeConfig.fetchRuntimeConfigStatus(appState.connection.serverAddress);
                const workspaceRoot = status?.workspace?.root || '';
                if (workspaceRoot) {
                    dom.workspaceRootInput.value = workspaceRoot;
                }
            } catch (error) {
                console.warn('Failed to load workspace root:', error);
            }
        };

        const openModal = () => {
            modalOpen = true;
            dom.serverIpInput.value = appState.connection.serverAddress;
            if (dom.observerModeSelect) dom.observerModeSelect.value = appState.observer.mode;
            if (dom.accessTokenInput) {
                dom.accessTokenInput.value = storage.getAccessToken();
                dom.accessTokenInput.type = 'password';
            }
            if (dom.workspaceRootInput) {
                dom.workspaceRootInput.value = '';
            }
            updateAdminLink();
            loadWorkspaceRoot();

            setStatus(appEnv.isBridge
                ? 'Bridge 模式仅保存后端地址、观察模式和访问令牌。'
                : '运行时模型配置已经迁移到独立的 Admin 页面。');
            if (dom.settingsBackdrop) {
                dom.settingsBackdrop.style.display = 'block';
            }
            dom.settingsModal.style.display = 'block';
            dom.settingsModal.focus?.();
            setTimeout(() => dom.serverIpInput?.focus(), 0);
        };

        const closeModal = () => {
            modalOpen = false;
            dom.settingsModal.style.display = 'none';
            if (dom.settingsBackdrop) {
                dom.settingsBackdrop.style.display = 'none';
            }
            dom.settingsBtn.focus?.();
        };

        const saveSettings = async () => {
            const newAddress = dom.serverIpInput.value.trim();
            const newMode = dom.observerModeSelect ? dom.observerModeSelect.value : 'general';
            const accessToken = dom.accessTokenInput ? dom.accessTokenInput.value : '';
            const workspaceRoot = dom.workspaceRootInput ? dom.workspaceRootInput.value.trim() : '';

            if (!newAddress) {
                setStatus('请填写后端地址。', true);
                dom.serverIpInput.focus();
                return;
            }

            if (dom.saveSettingsBtn) {
                dom.saveSettingsBtn.disabled = true;
            }
            setStatus('正在保存设置...');

            const prevAddress = appState.connection.serverAddress;
            storage.setServerAddress(newAddress);
            storage.setObserverMode(newMode);
            storage.setAccessToken(accessToken);
            appState.connection.serverAddress = newAddress;
            appState.observer.mode = newMode;

            try {
                if (workspaceRoot) {
                    await runtimeConfig.applyRuntimeConfig(newAddress, { workspace_root: workspaceRoot });
                }
            } catch (error) {
                setStatus(error.message || '工作目录保存失败。', true);
                if (dom.saveSettingsBtn) {
                    dom.saveSettingsBtn.disabled = false;
                }
                return;
            }

            setStatus('设置已保存。');

            if (newAddress !== prevAddress) {
                setTimeout(() => location.reload(), 350);
                return;
            }

            if (dom.saveSettingsBtn) {
                dom.saveSettingsBtn.disabled = false;
            }
            setTimeout(closeModal, 350);
        };

        dom.serverIpInput?.addEventListener('input', updateAdminLink);
        dom.selectWorkspaceDirBtn?.addEventListener('click', async () => {
            const selectedPath = await selectWorkspaceDirectory();
            if (selectedPath && dom.workspaceRootInput) {
                dom.workspaceRootInput.value = selectedPath;
                setStatus('');
            }
        });
        dom.serverIpInput?.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                saveSettings();
            }
        });
        dom.workspaceRootInput?.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                saveSettings();
            }
        });
        dom.accessTokenInput?.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                saveSettings();
            }
        });
        dom.toggleTokenVisibilityBtn?.addEventListener('click', () => {
            if (!dom.accessTokenInput) {
                return;
            }
            const visible = dom.accessTokenInput.type === 'text';
            dom.accessTokenInput.type = visible ? 'password' : 'text';
            const icon = dom.toggleTokenVisibilityBtn.querySelector('i');
            if (icon) {
                icon.className = visible ? 'bi bi-eye' : 'bi bi-eye-slash';
            }
        });
        dom.settingsBtn.addEventListener('click', openModal);
        dom.settingsBackdrop?.addEventListener('click', closeModal);
        dom.cancelSettingsBtn?.addEventListener('click', closeModal);
        dom.saveSettingsBtn?.addEventListener('click', saveSettings);
        document.addEventListener('keydown', (event) => {
            if (modalOpen && event.key === 'Escape') {
                closeModal();
            }
        });
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
