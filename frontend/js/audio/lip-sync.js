(() => {
    let currentLipSyncTimer = null;

    const start = (audioOrDuration) => {
        const live2dModel = window.live2d?.getModel();
        if (!live2dModel) return;
        stop();

        let durationMs = 0;
        if (typeof audioOrDuration === 'number') {
            durationMs = audioOrDuration * 1000;
        } else if (audioOrDuration && typeof audioOrDuration.duration === 'number') {
            durationMs = audioOrDuration.duration * 1000;
        }

        const startTime = Date.now();
        currentLipSyncTimer = setInterval(() => {
            const elapsed = Date.now() - startTime;
            if (elapsed >= durationMs) {
                stop();
                return;
            }
            const value = Math.random() * 0.8;
            if (live2dModel && live2dModel.internalModel) {
                live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', value);
            }
        }, 100);
    };

    const stop = () => {
        if (currentLipSyncTimer) {
            clearInterval(currentLipSyncTimer);
            currentLipSyncTimer = null;
        }
        const live2dModel = window.live2d?.getModel();
        if (live2dModel && live2dModel.internalModel) {
            live2dModel.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', 0);
        }
    };

    window.lipSync = { start, stop };
})();
