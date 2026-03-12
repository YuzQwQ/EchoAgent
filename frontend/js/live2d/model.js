(() => {
    let live2dModel = null;
    let app = null;

    const init = async ({ onError } = {}) => {
        try {
            app = new PIXI.Application({
                view: document.getElementById('live2d-canvas'),
                autoStart: true,
                backgroundAlpha: 0,
                resizeTo: document.getElementById('live2d-container'),
                resolution: window.devicePixelRatio || 1,
                autoDensity: true
            });

            const modelPath = 'assets/live2d/hiyori/hiyori_pro_zh/runtime/hiyori_pro_t11.model3.json';
            const Live2DModel = window.PIXI.live2d.Live2DModel;
            live2dModel = await Live2DModel.from(modelPath, {});
            app.stage.addChild(live2dModel);

            if (window.live2dMotions?.bindTapMotion) {
                window.live2dMotions.bindTapMotion(live2dModel);
            }
            if (window.live2dFocus?.init) {
                window.live2dFocus.init({ app, model: live2dModel });
            }
            if (window.live2dFocus?.resizeModel) {
                window.live2dFocus.resizeModel({ app, model: live2dModel });
            }
            if (window.live2dFocus?.bindResize) {
                window.live2dFocus.bindResize({ app, model: live2dModel });
            }
            if (window.live2dMotions?.stopAll) {
                window.live2dMotions.stopAll(live2dModel);
            }
            console.log('Live2D Model Loaded');
        } catch (error) {
            console.error('Failed to load Live2D model:', error);
            onError?.(`Live2D 加载失败: ${error.message}`);
        }
    };

    const triggerMotion = (emotion) => {
        if (!live2dModel) return;
        if (window.live2dMotions?.trigger) {
            window.live2dMotions.trigger(live2dModel, emotion);
        }
    };

    const getModel = () => live2dModel;
    const getApp = () => app;

    window.live2d = {
        init,
        triggerMotion,
        getModel,
        getApp
    };
})();
