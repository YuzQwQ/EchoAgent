(() => {
    const dom = window.dom;
    const showBubble = window.showBubble;
    if (!dom?.micBtn) return;

    const getRuntime = () => window.runtime || {};
    const getWs = () => (getRuntime().getWs ? getRuntime().getWs() : null);
    const getIsConnected = () => (getRuntime().isConnected ? getRuntime().isConnected() : false);
    const getTtsEnabled = () => (getRuntime().getTtsEnabled ? getRuntime().getTtsEnabled() : false);

    let recorder = new WavRecorder();
    let isRecording = false;
    let recordStartTime = 0;

    const startRecording = async () => {
        if (isRecording) return;
        try {
            dom.micBtn.classList.add('active');
            showBubble?.('正在听...', 0);
            isRecording = true;
            recordStartTime = Date.now();
            await recorder.start();
        } catch (e) {
            console.error('Failed to start recording:', e);
            resetMicBtn();
        }
    };

    const stopRecording = async () => {
        if (!isRecording) return;
        if (Date.now() - recordStartTime < 500) {
            await recorder.stop();
            resetMicBtn();
            return;
        }

        try {
            showBubble?.('正在识别...', 0);
            const wavBlob = await recorder.stop();
            resetMicBtn();
            sendAudio(wavBlob);
        } catch (e) {
            console.error('Failed to stop recording:', e);
            resetMicBtn();
        }
    };

    function resetMicBtn() {
        isRecording = false;
        dom.micBtn.classList.remove('active');
    }

    function sendAudio(blob) {
        if (!getIsConnected()) {
            showBubble?.('Error: 未连接到服务器', 3000);
            return;
        }

        const ws = getWs();
        if (!ws) return;

        const reader = new FileReader();
        reader.onload = function(e) {
            const base64Data = e.target.result;
            ws.send(JSON.stringify({
                type: 'audio',
                content: base64Data,
                enable_tts: getTtsEnabled()
            }));
        };
        reader.readAsDataURL(blob);
    }

    dom.micBtn.addEventListener('mousedown', startRecording);
    dom.micBtn.addEventListener('mouseup', stopRecording);
    dom.micBtn.addEventListener('mouseleave', () => {
        if (isRecording) stopRecording();
    });
    dom.micBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecording();
    });
    dom.micBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecording();
    });
})();
