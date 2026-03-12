(() => {
    const bindTapMotion = (model) => {
        if (!model) return;
        model.interactive = true;
        model.buttonMode = true;
        model.on('pointertap', () => {
            model.internalModel.motionManager.startRandomMotion('Tap');
        });
    };

    const stopAll = (model) => {
        if (!model) return;
        model.internalModel.motionManager.stopAllMotions();
    };

    const trigger = (model, emotion) => {
        if (!model) return;
        let candidates = [];
        switch (emotion) {
            case 'happy':
                candidates = [
                    { g: 'FlickUp', i: 0 },
                    { g: 'Tap', i: 1 },
                    { g: 'Flick', i: 0 }
                ];
                break;
            case 'sad':
                candidates = [
                    { g: 'FlickDown', i: 0 },
                    { g: 'Flick@Body', i: 0 }
                ];
                break;
            case 'angry':
            case 'serious':
                candidates = [{ g: 'Tap@Body', i: 0 }];
                break;
            case 'surprised':
                candidates = [
                    { g: 'Tap', i: 0 },
                    { g: 'Idle', i: 1 }
                ];
                break;
            case 'shy':
                candidates = [{ g: 'Flick', i: 0 }];
                break;
            case 'relaxed':
            case 'idle':
            default:
                candidates = [
                    { g: 'Idle', i: 0 },
                    { g: 'Idle', i: 2 }
                ];
        }

        if (candidates.length > 0) {
            const c = candidates[Math.floor(Math.random() * candidates.length)];
            model.internalModel.motionManager.startMotion(c.g, c.i, 3);
        }
    };

    window.live2dMotions = {
        bindTapMotion,
        stopAll,
        trigger
    };
})();
