(() => {
    const dom = window.dom;
    const live2d = window.live2d;
    const showSubtitle = window.showSubtitle;
    const electronBridge = window.electronBridge;
    const ipcRenderer = electronBridge ? electronBridge.ipcRenderer : null;
    const isElectronEnv = !!ipcRenderer;

    if (!dom?.motionBtn) return;

    const openMotionWindow = () => {
        if (!isElectronEnv || !ipcRenderer) {
            showSubtitle?.('浏览器模式暂不支持动作演示窗口。', 2000);
            return;
        }
        const live2dModel = live2d?.getModel();
        if (!live2dModel) return;

        let motions = null;
        if (live2dModel.internalModel.settings.json.FileReferences.Motions) {
            motions = live2dModel.internalModel.settings.json.FileReferences.Motions;
        } else if (live2dModel.internalModel.motionManager.definitions) {
            motions = live2dModel.internalModel.motionManager.definitions;
        }

        if (motions) {
            ipcRenderer.send('open-motion-window', motions);
        } else {
            showSubtitle?.('未找到动作定义', 2000);
        }
    };

    dom.motionBtn.addEventListener('click', () => openMotionWindow());

    if (ipcRenderer) {
        ipcRenderer.on('play-motion', (event, { group, index, name }) => {
            const live2dModel = live2d?.getModel();
            if (!live2dModel) return;
            showSubtitle?.(`演示动作: ${group} / ${name}`, 2000);
            live2dModel.internalModel.motionManager.startMotion(group, index, 3);
        });

        ipcRenderer.on('global-mouse-move', (event, { x, y, globalX, globalY }) => {
            const live2dModel = live2d?.getModel();
            if (window.live2dFocus?.focusByGlobalPoint) {
                window.live2dFocus.focusByGlobalPoint({ model: live2dModel, x, y, globalX, globalY });
            }
        });
    }
})();
