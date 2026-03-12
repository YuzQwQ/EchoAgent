(() => {
    const OBSERVER_ACTIVE_INTERVAL_MS = 100;
    const OBSERVER_IDLE_INTERVAL_MS = 250;
    const OBSERVER_PIXEL_DIFF_THRESHOLD = 25;
    const OBSERVER_CHANGE_LIGHT = 0.003;
    const OBSERVER_CHANGE_MEDIUM = 0.01;
    const OBSERVER_CHANGE_STRONG = 0.03;
    const OBSERVER_STABLE_FRAMES = 2;
    const OBSERVER_IDLE_FRAMES = 6;
    const OBSERVER_EVENT_WINDOW_MS = 800;
    const OBSERVER_MIN_INTERVAL_MS = 2500;
    const OBSERVER_STRONG_MIN_INTERVAL_MS = 800;
    const OBSERVER_DEBOUNCE_MS = 1500;
    const OBSERVER_MAX_WAIT_MS = 6000;

    let isRunning = false;
    let observerTimer = null;
    let observerPrevGray = null;
    let observerStableCount = 0;
    let observerIdleCount = 0;
    let observerEventActive = false;
    let observerEventEnd = 0;
    let observerBestFrame = null;
    let observerBestChange = 0;
    let observerLastSendTime = 0;
    let observerPendingFrame = null;
    let observerPendingEventType = '';
    let observerLastEventType = '';
    let observerLastEventTime = 0;
    let observerSustainedStart = 0;
    let observerEventType = '';
    let observerNextIntervalMs = OBSERVER_ACTIVE_INTERVAL_MS;
    let onSend = null;

    const resetState = () => {
        observerPrevGray = null;
        observerStableCount = 0;
        observerIdleCount = 0;
        observerEventActive = false;
        observerEventEnd = 0;
        observerBestFrame = null;
        observerBestChange = 0;
        observerLastSendTime = 0;
        observerPendingFrame = null;
        observerPendingEventType = '';
        observerLastEventType = '';
        observerLastEventTime = 0;
        observerSustainedStart = 0;
        observerEventType = '';
        observerNextIntervalMs = OBSERVER_ACTIVE_INTERVAL_MS;
    };

    const start = ({ onSend: onSendCallback } = {}) => {
        if (isRunning) return;
        isRunning = true;
        onSend = typeof onSendCallback === 'function' ? onSendCallback : null;
        scheduleObserverAnalysis(0);
    };

    const stop = () => {
        isRunning = false;
        if (observerTimer) {
            clearTimeout(observerTimer);
            observerTimer = null;
        }
        resetState();
    };

    const scheduleObserverAnalysis = (delayMs) => {
        if (!isRunning) return;
        if (observerTimer) clearTimeout(observerTimer);
        observerTimer = setTimeout(observerAnalyzeFrame, delayMs);
    };

    const observerAnalyzeFrame = () => {
        if (!isRunning) return;
        const capture = window.observerCapture;
        const observerVideo = capture?.getVideo?.();
        const observerAnalysisCtx = capture?.getAnalysisContext?.();
        const size = capture?.getAnalysisSize?.();
        if (!observerVideo || !observerAnalysisCtx || !size) {
            scheduleObserverAnalysis(OBSERVER_ACTIVE_INTERVAL_MS);
            return;
        }
        if (observerVideo.readyState < 2) {
            scheduleObserverAnalysis(OBSERVER_ACTIVE_INTERVAL_MS);
            return;
        }

        observerAnalysisCtx.drawImage(observerVideo, 0, 0, size.width, size.height);
        const imageData = observerAnalysisCtx.getImageData(0, 0, size.width, size.height);
        const data = imageData.data;
        const totalPixels = size.width * size.height;
        let prev = observerPrevGray;
        if (!prev || prev.length !== totalPixels) {
            prev = new Uint8Array(totalPixels);
        }
        let changed = 0;
        let index = 0;
        for (let i = 0; i < data.length; i += 4) {
            const gray = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) | 0;
            const diff = Math.abs(gray - prev[index]);
            if (diff > OBSERVER_PIXEL_DIFF_THRESHOLD) {
                changed += 1;
            }
            prev[index] = gray;
            index += 1;
        }
        observerPrevGray = prev;
        const changeRatio = changed / totalPixels;
        const changeLevel = getObserverChangeLevel(changeRatio);
        const now = performance.now();

        if (observerPendingFrame) {
            const pendingMinInterval = observerPendingEventType === 'strong' ? OBSERVER_STRONG_MIN_INTERVAL_MS : OBSERVER_MIN_INTERVAL_MS;
            const pendingDebounced = observerPendingEventType === observerLastEventType && now - observerLastEventTime < OBSERVER_DEBOUNCE_MS;
            if (now - observerLastSendTime >= pendingMinInterval && !pendingDebounced) {
                const sent = emitFrame(observerPendingFrame, observerPendingEventType, now);
                if (sent) {
                    observerPendingFrame = null;
                    observerPendingEventType = '';
                }
            }
        }

        if (changeLevel === 'idle') {
            observerStableCount = 0;
            observerIdleCount += 1;
        } else {
            observerIdleCount = 0;
            observerStableCount = Math.min(observerStableCount + 1, OBSERVER_STABLE_FRAMES);
        }

        observerNextIntervalMs = (observerIdleCount >= OBSERVER_IDLE_FRAMES && !observerEventActive)
            ? OBSERVER_IDLE_INTERVAL_MS
            : OBSERVER_ACTIVE_INTERVAL_MS;

        if (changeLevel !== 'idle') {
            if (!observerSustainedStart) observerSustainedStart = now;
        } else {
            observerSustainedStart = 0;
        }

        if (!observerEventActive && observerStableCount >= OBSERVER_STABLE_FRAMES && (changeLevel === 'medium' || changeLevel === 'strong')) {
            observerEventActive = true;
            observerEventEnd = now + OBSERVER_EVENT_WINDOW_MS;
            observerBestFrame = null;
            observerBestChange = 0;
            observerEventType = changeLevel;
        }
        if (changeLevel === 'strong' && !observerEventActive && observerStableCount >= 1) {
            const frame = capture?.captureFrame?.();
            attemptSendObserverFrame(frame, 'strong', now);
            observerStableCount = 0;
            observerSustainedStart = 0;
        }

        if (observerEventActive) {
            if (changeRatio > observerBestChange) {
                observerBestChange = changeRatio;
                observerBestFrame = capture?.captureFrame?.();
            }
            if (now >= observerEventEnd || (changeLevel === 'strong' && observerBestChange >= OBSERVER_CHANGE_STRONG)) {
                observerEventActive = false;
                observerStableCount = 0;
                if (observerBestFrame) {
                    attemptSendObserverFrame(observerBestFrame, observerEventType, now);
                }
                observerBestFrame = null;
                observerBestChange = 0;
            }
        }

        if (!observerEventActive && observerSustainedStart && now - observerSustainedStart >= OBSERVER_MAX_WAIT_MS) {
            const frame = capture?.captureFrame?.();
            attemptSendObserverFrame(frame, 'medium', now);
            observerSustainedStart = now;
        }

        scheduleObserverAnalysis(observerNextIntervalMs);
    };

    const getObserverChangeLevel = (changeRatio) => {
        if (changeRatio >= OBSERVER_CHANGE_STRONG) return 'strong';
        if (changeRatio >= OBSERVER_CHANGE_MEDIUM) return 'medium';
        if (changeRatio >= OBSERVER_CHANGE_LIGHT) return 'light';
        return 'idle';
    };

    const attemptSendObserverFrame = (dataUrl, eventType, now) => {
        if (!dataUrl) return;
        const minInterval = eventType === 'strong' ? OBSERVER_STRONG_MIN_INTERVAL_MS : OBSERVER_MIN_INTERVAL_MS;
        const debounced = eventType === observerLastEventType && now - observerLastEventTime < OBSERVER_DEBOUNCE_MS;
        if (now - observerLastSendTime < minInterval || debounced) {
            observerPendingFrame = dataUrl;
            observerPendingEventType = eventType;
            return;
        }
        emitFrame(dataUrl, eventType, now);
    };

    const emitFrame = (dataUrl, eventType, now) => {
        if (!dataUrl || !onSend) return false;
        const sent = onSend({ dataUrl, eventType });
        if (sent) {
            observerLastSendTime = now;
            observerLastEventType = eventType;
            observerLastEventTime = now;
        }
        return sent;
    };

    window.observerAnalyzer = {
        start,
        stop
    };
})();
