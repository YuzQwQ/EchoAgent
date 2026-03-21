(() => {
    const dom = {
        dragOverlay: document.getElementById('drag-overlay'),
        live2dContainer: document.getElementById('live2d-container'),
        live2dCanvas: document.getElementById('live2d-canvas'),
        hudLayer: document.getElementById('hud-layer'),
        statusChip: document.getElementById('status-chip'),
        statusDot: document.getElementById('status-dot'),
        statusText: document.getElementById('status-text'),
        subtitleBar: document.getElementById('subtitle-bar'),
        inputOverlay: document.getElementById('input-overlay'),
        miniInput: document.getElementById('mini-input'),
        miniSendBtn: document.getElementById('mini-send-btn'),
        controlPanel: document.getElementById('control-panel'),
        toggleInputBtn: document.getElementById('toggle-input-btn'),
        micBtn: document.getElementById('mic-btn'),
        observerBtn: document.getElementById('observer-btn'),
        motionBtn: document.getElementById('motion-btn'),
        ttsBtn: document.getElementById('tts-btn'),
        settingsBtn: document.getElementById('settings-btn'),
        closeBtn: document.getElementById('close-btn'),
        imageUpload: document.getElementById('image-upload'),
        imgBtn: document.getElementById('img-btn'),
        settingsModal: document.getElementById('settings-modal'),
        serverIpInput: document.getElementById('server-ip-input'),
        observerModeSelect: document.getElementById('observer-mode-select'),
        accessTokenInput: document.getElementById('access-token-input'),
        adminPanelInfo: document.getElementById('admin-panel-info'),
        openAdminPanelLink: document.getElementById('open-admin-panel-link'),
        runtimeConfigStatus: document.getElementById('runtime-config-status'),
        saveSettingsBtn: document.getElementById('save-settings-btn'),
        cancelSettingsBtn: document.getElementById('cancel-settings-btn'),
        chatSection: document.getElementById('chat-section'),
        chatContainer: document.getElementById('chat-container')
    };

    window.dom = dom;
})();
