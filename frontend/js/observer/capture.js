(() => {
    let observerStream = null;
    let observerVideo = null;
    let observerAnalysisCanvas = null;
    let observerAnalysisCtx = null;
    let observerFrameCanvas = null;
    let observerFrameCtx = null;

    const OBSERVER_ANALYSIS_WIDTH = 160;
    const OBSERVER_ANALYSIS_HEIGHT = 90;
    const OBSERVER_SEND_MAX_WIDTH = 1280;
    const OBSERVER_SEND_MAX_HEIGHT = 720;
    const OBSERVER_SEND_QUALITY = 0.7;

    const init = async ({ ipcRenderer, getIsConnected } = {}) => {
        if (getIsConnected && !getIsConnected()) return;
        if (observerStream) return;
        if (!ipcRenderer) throw new Error('IPC not available');
        const sourceId = await ipcRenderer.invoke('get-screen-source-id');
        if (!sourceId) throw new Error('No screen source found');

        observerStream = await navigator.mediaDevices.getUserMedia({
            audio: false,
            video: {
                mandatory: {
                    chromeMediaSource: 'desktop',
                    chromeMediaSourceId: sourceId,
                    maxWidth: 1920,
                    maxHeight: 1080
                }
            }
        });

        observerVideo = document.createElement('video');
        observerVideo.srcObject = observerStream;

        await new Promise((resolve) => {
            observerVideo.onloadedmetadata = () => {
                observerVideo.play();
                resolve();
            };
        });

        observerAnalysisCanvas = document.createElement('canvas');
        observerAnalysisCanvas.width = OBSERVER_ANALYSIS_WIDTH;
        observerAnalysisCanvas.height = OBSERVER_ANALYSIS_HEIGHT;
        observerAnalysisCtx = observerAnalysisCanvas.getContext('2d');
        observerFrameCanvas = document.createElement('canvas');
        observerFrameCtx = observerFrameCanvas.getContext('2d');
    };

    const stop = () => {
        if (observerStream) {
            observerStream.getTracks().forEach(track => track.stop());
        }
        observerStream = null;
        observerVideo = null;
        observerAnalysisCanvas = null;
        observerAnalysisCtx = null;
        observerFrameCanvas = null;
        observerFrameCtx = null;
    };

    const getVideo = () => observerVideo;
    const getAnalysisContext = () => observerAnalysisCtx;
    const getAnalysisSize = () => ({
        width: OBSERVER_ANALYSIS_WIDTH,
        height: OBSERVER_ANALYSIS_HEIGHT
    });

    const captureFrame = () => {
        if (!observerVideo || !observerFrameCanvas || !observerFrameCtx) return null;
        const width = observerVideo.videoWidth || 1920;
        const height = observerVideo.videoHeight || 1080;
        const scale = Math.min(1, OBSERVER_SEND_MAX_WIDTH / width, OBSERVER_SEND_MAX_HEIGHT / height);
        const targetWidth = Math.max(1, Math.round(width * scale));
        const targetHeight = Math.max(1, Math.round(height * scale));
        observerFrameCanvas.width = targetWidth;
        observerFrameCanvas.height = targetHeight;
        observerFrameCtx.drawImage(observerVideo, 0, 0, targetWidth, targetHeight);
        return observerFrameCanvas.toDataURL('image/jpeg', OBSERVER_SEND_QUALITY);
    };

    window.observerCapture = {
        init,
        stop,
        getVideo,
        getAnalysisContext,
        getAnalysisSize,
        captureFrame
    };
})();
