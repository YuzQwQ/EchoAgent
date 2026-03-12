(() => {
    const updateConnectionBadge = (online, text) => {
        const statusDot = window.dom?.statusDot;
        const statusText = window.dom?.statusText;
        if (!statusDot || !statusText) return;
        statusDot.classList.toggle('online', !!online);
        statusText.textContent = text || (online ? 'Echo 在线' : 'Echo 离线');
    };

    window.updateConnectionBadge = updateConnectionBadge;
})();
