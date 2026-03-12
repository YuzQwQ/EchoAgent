(() => {
    const resizeModel = ({ app, model } = {}) => {
        if (!app || !model) return;
        model.scale.set(1);
        const modelWidth = model.width;
        const modelHeight = model.height;
        const screenWidth = app.screen.width;
        const screenHeight = app.screen.height;
        const targetHeight = screenHeight * 2.5;
        const scale = targetHeight / modelHeight;
        model.scale.set(scale);
        model.x = (screenWidth - (modelWidth * scale)) / 2;
        model.y = screenHeight * 0.1;
    };

    const bindResize = ({ app, model } = {}) => {
        if (!app || !model) return;
        const resize = () => resizeModel({ app, model });
        resize();
        window.addEventListener('resize', () => setTimeout(resize, 10));
        app.renderer.on('resize', resize);
    };

    const focusByGlobalPoint = ({ model, x, y, globalX, globalY } = {}) => {
        if (!model || !model.internalModel) return;
        if (model.autoInteract) model.autoInteract = false;
        try {
            if (globalX === undefined || globalY === undefined) {
                if (typeof model.focus === 'function') {
                    model.focus(x, y);
                }
                return;
            }

            const screenW = window.screen.width;
            const screenH = window.screen.height;
            const viewX = (globalX / screenW) * 2.0 - 1.0;
            const viewY = -((globalY / screenH) * 2.0 - 1.0);

            if (model.internalModel.focusController) {
                model.internalModel.focusController.focus(viewX, viewY);
            }
        } catch (e) {
            console.error('Focus error:', e);
        }
    };

    const init = ({ app, model } = {}) => {
        if (!app || !model) return;
        bindResize({ app, model });
    };

    window.live2dFocus = {
        init,
        bindResize,
        resizeModel,
        focusByGlobalPoint
    };
})();
