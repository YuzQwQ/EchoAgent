(() => {
    const createClient = () => {
        let ws = null;
        let reconnectTimer = null;
        let handlers = {};
        let textBuffer = '';
        let chunkActive = false;

        const connect = (options) => {
            handlers = options || {};
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }

            const getServerAddress = handlers.getServerAddress || (() => '');
            const normalize = handlers.normalizeServerAddress || ((value) => ({ host: value, port: 80 }));
            const { host, port } = normalize(getServerAddress());
            const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
            ws = new WebSocket(`${wsProtocol}://${host}:${port}/ws/chat`);
            handlers.onWs?.(ws);

            textBuffer = '';
            chunkActive = false;
            handlers.onStatus?.(false, 'Echo 连接中...');

            ws.onopen = () => {
                handlers.onConnectedChange?.(true);
                handlers.onStatus?.(true, 'Echo 在线');
                handlers.onSystemMessage?.('Echo 已上线！！');
                handlers.onSendEnabled?.(true);
            };

            ws.onmessage = (event) => {
                let data = null;
                try {
                    data = JSON.parse(event.data);
                } catch (e) {
                    console.error('WebSocket message parse error:', e);
                    return;
                }

                if (data.type === 'user_input') {
                    handlers.onUserInput?.(data.content);
                    return;
                }
                if (data.type === 'chunk') {
                    if (!chunkActive) {
                        chunkActive = true;
                        textBuffer = '';
                        handlers.onChunkStart?.();
                    }

                    textBuffer += data.content || '';
                    const tagRegex = /\[emotion:\s*([^[\]]+?)\]/i;

                    while (true) {
                        const match = textBuffer.match(tagRegex);
                        if (!match) break;

                        const [fullTag, rawEmotion] = match;
                        const emotion = rawEmotion.trim();
                        const tagIndex = match.index;
                        const contentBefore = textBuffer.substring(0, tagIndex);
                        if (contentBefore) {
                            handlers.onChunkText?.(contentBefore);
                        }
                        handlers.onEmotion?.(emotion);
                        textBuffer = textBuffer.substring(tagIndex + fullTag.length);
                    }

                    let safeEndIndex = textBuffer.length;
                    const lastOpen = textBuffer.lastIndexOf('[');
                    if (lastOpen >= 0) {
                        const tail = textBuffer.substring(lastOpen);
                        const target = '[emotion:';
                        if (target.startsWith(tail) || tail.startsWith(target)) {
                            safeEndIndex = lastOpen;
                        }
                    }

                    const contentToFlush = textBuffer.substring(0, safeEndIndex);
                    textBuffer = textBuffer.substring(safeEndIndex);
                    if (contentToFlush) {
                        handlers.onChunkText?.(contentToFlush);
                    }
                    return;
                }
                if (data.type === 'audio_stream') {
                    handlers.onAudioStream?.(data);
                    return;
                }
                if (data.type === 'audio') {
                    handlers.onAudio?.(data);
                    return;
                }
                if (data.type === 'done') {
                    if (textBuffer) {
                        handlers.onChunkText?.(textBuffer);
                        textBuffer = '';
                    }
                    chunkActive = false;
                    handlers.onDone?.();
                    return;
                }
                if (data.type === 'error') {
                    handlers.onErrorMessage?.(data.content);
                    chunkActive = false;
                }
            };

            ws.onclose = () => {
                handlers.onConnectedChange?.(false);
                handlers.onStatus?.(false, 'Echo 离线，重连中...');
                handlers.onSystemMessage?.('与 Echo 断开连接，正在尝试重连...');
                handlers.onSendEnabled?.(false);
                reconnectTimer = setTimeout(() => connect(handlers), 3000);
            };

            ws.onerror = (err) => {
                console.error('WebSocket Error:', err);
                handlers.onStatus?.(false, 'Echo 连接异常');
            };
        };

        const sendJson = (payload) => {
            if (!ws || ws.readyState !== 1) return false;
            ws.send(JSON.stringify(payload));
            return true;
        };

        const sendText = (text) => {
            return sendJson({ type: 'text', content: text, role: 'user' });
        };

        const sendImage = (content) => {
            return sendJson({ type: 'image', content });
        };

        const sendRaw = (payload) => {
            return sendJson(payload);
        };

        const getWs = () => ws;

        return { connect, sendText, sendImage, sendRaw, getWs };
    };

    window.wsClient = createClient();
})();
