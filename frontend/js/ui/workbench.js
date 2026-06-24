(() => {
    const dom = window.dom;
    const store = window.messageStore;
    const traceStore = window.traceStore;
    const wsClient = window.wsClient;
    const electron = window.require?.('electron');
    const ipcRenderer = electron?.ipcRenderer;

    if (!dom || !store) {
        return;
    }

    let mode = 'daily';
    let traceDetached = false;
    const maxInputHeight = 8 * 24 + 22;
    const traceHeight = {
        min: 120,
        maxRatio: 0.6,
        current: 180
    };

    const escapeHtml = (value) => String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const labelForRole = (role) => {
        if (role === 'user') return '你';
        if (role === 'assistant') return 'Echo';
        if (role === 'system') return '系统';
        if (role === 'tool_call') return '工具调用';
        if (role === 'tool_result') return '工具结果';
        return role || '消息';
    };

    const setShellMode = async (nextMode) => {
        try {
            if (ipcRenderer) {
                await ipcRenderer.invoke('set-shell-mode', nextMode);
            }
        } catch (error) {
            console.warn('Failed to set shell mode:', error);
        }
    };

    const refreshLive2DLayout = () => {
        window.dispatchEvent(new Event('resize'));
        requestAnimationFrame(() => window.live2d?.resize?.());
        setTimeout(() => window.live2d?.resize?.(), 80);
        setTimeout(() => window.live2d?.resize?.(), 220);
    };

    const renderMessages = (messages) => {
        if (!dom.chatContainer) return;

        if (!messages.length) {
            dom.chatContainer.innerHTML = '<div class="workbench-empty">当前还没有会话。日常模式和工作台会共享同一份运行期历史。</div>';
            return;
        }

        dom.chatContainer.innerHTML = messages.map((message) => {
            const role = message.role || 'system';
            const content = escapeHtml(message.content || '').replace(/\n/g, '<br>');
            const streaming = message.streaming ? '<span class="message-streaming">生成中</span>' : '';
            return `
                <article class="message-row ${role}">
                    <div class="message-meta">
                        <span>${labelForRole(role)}</span>
                        ${streaming}
                    </div>
                    <div class="message-bubble">${content || '<span class="message-muted">...</span>'}</div>
                </article>
            `;
        }).join('');

        dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
    };

    const renderRecentHistory = () => {
        if (!dom.recentHistoryList) return;
        const messages = store.getRecentMessages(10);
        if (!messages.length) {
            dom.recentHistoryList.innerHTML = '<div class="recent-history-empty">暂无近期消息。</div>';
            return;
        }
        dom.recentHistoryList.innerHTML = messages.map((message) => `
            <div class="recent-history-item ${message.role}">
                <div class="recent-history-role">${labelForRole(message.role)}</div>
                <div class="recent-history-text">${escapeHtml(message.content || '').replace(/\n/g, '<br>')}</div>
            </div>
        `).join('');
    };

    const visibleTraceEvents = () => {
        const showDebug = Boolean(dom.traceDebugToggle?.checked);
        const events = traceStore?.getEvents?.() || [];
        return events.filter((event) => showDebug || event.level !== 'debug');
    };

    const formatTraceTime = (timestamp) => {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleTimeString([], { hour12: false });
    };

    const traceDetails = (event) => {
        const keys = [
            'tool',
            'action',
            'ok',
            'path',
            'error_type',
            'round',
            'tool_calls_count',
            'elapsed_ms',
            'model',
            'category',
            'audio_size'
        ];
        return keys
            .filter((key) => event[key] !== undefined && event[key] !== null && event[key] !== '')
            .map((key) => `${key}=${event[key]}`)
            .join(' ');
    };

    const renderTraceEvents = () => {
        if (!dom.traceList) return;
        const events = visibleTraceEvents();
        if (!events.length) {
            dom.traceList.innerHTML = '<div class="trace-empty">暂无运行日志。</div>';
            return;
        }

        dom.traceList.innerHTML = events.map((event) => {
            const level = event.level || 'info';
            const detail = traceDetails(event);
            const preview = event.content_preview ? `<div class="trace-preview">${escapeHtml(event.content_preview)}</div>` : '';
            return `
                <div class="trace-row ${level}">
                    <span class="trace-time">${escapeHtml(formatTraceTime(event.timestamp))}</span>
                    <span class="trace-level">${escapeHtml(level)}</span>
                    <span class="trace-event">${escapeHtml(event.event || 'event')}</span>
                    <span class="trace-message">${escapeHtml(event.message || '')}</span>
                    ${detail ? `<span class="trace-detail">${escapeHtml(detail)}</span>` : ''}
                    ${preview}
                </div>
            `;
        }).join('');

        dom.traceList.scrollTop = dom.traceList.scrollHeight;
    };

    const formatTraceForClipboard = () => {
        return visibleTraceEvents().map((event) => {
            const detail = traceDetails(event);
            const parts = [
                `[${formatTraceTime(event.timestamp)}]`,
                `[${event.level || 'info'}]`,
                event.event || 'event',
                event.message || ''
            ];
            if (detail) parts.push(detail);
            if (event.content_preview) parts.push(`preview=${event.content_preview}`);
            return parts.filter(Boolean).join(' ');
        }).join('\n');
    };

    const syncDetachedTraceWindow = () => {
        if (!ipcRenderer || !traceStore?.getEvents) return;
        ipcRenderer.send('trace-window-update', {
            events: traceStore.getEvents()
        });
    };

    const setTraceDetached = (detached) => {
        traceDetached = !!detached;
        document.body.classList.toggle('trace-detached', traceDetached);
        if (!traceDetached) {
            setTraceHeight(traceHeight.current);
            renderTraceEvents();
        }
    };

    const openDetachedTraceWindow = async () => {
        if (!ipcRenderer) return;
        try {
            await ipcRenderer.invoke('open-trace-window');
            setTraceDetached(true);
            syncDetachedTraceWindow();
        } catch (error) {
            console.warn('Failed to open trace window:', error);
        }
    };

    const clampTraceHeight = (height) => {
        const shellHeight = dom.chatSection?.clientHeight || window.innerHeight || 720;
        const maxHeight = Math.max(traceHeight.min, Math.floor(shellHeight * traceHeight.maxRatio));
        return Math.min(Math.max(height, traceHeight.min), maxHeight);
    };

    const setTraceHeight = (height) => {
        traceHeight.current = clampTraceHeight(height);
        dom.chatSection?.style.setProperty('--trace-panel-height', `${traceHeight.current}px`);
    };

    const startTraceResize = (event) => {
        if (!dom.traceResizer || !dom.chatSection) return;
        event.preventDefault();
        const startY = event.clientY;
        const startHeight = traceHeight.current;
        dom.traceResizer.setPointerCapture?.(event.pointerId);
        document.body.classList.add('trace-resizing');

        const onMove = (moveEvent) => {
            setTraceHeight(startHeight + (moveEvent.clientY - startY));
        };

        const onUp = () => {
            document.body.classList.remove('trace-resizing');
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            window.removeEventListener('pointercancel', onUp);
        };

        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp, { once: true });
        window.addEventListener('pointercancel', onUp, { once: true });
    };

    const openWorkbench = async () => {
        mode = 'workbench';
        document.body.classList.add('mode-workbench');
        dom.workbenchBtn?.classList.add('active');
        dom.recentHistoryPanel && (dom.recentHistoryPanel.style.display = 'none');
        await setShellMode('workbench');
        refreshLive2DLayout();
        if (!traceDetached) {
            setTraceHeight(traceHeight.current);
        }
        renderMessages(store.getMessages());
        renderTraceEvents();
        setTimeout(() => dom.messageInput?.focus(), 0);
    };

    const closeWorkbench = async () => {
        mode = 'daily';
        document.body.classList.remove('mode-workbench');
        dom.workbenchBtn?.classList.remove('active');
        await setShellMode('daily');
        refreshLive2DLayout();
    };

    const toggleWorkbench = () => {
        if (mode === 'workbench') {
            closeWorkbench();
        } else {
            openWorkbench();
        }
    };

    const toggleRecentHistory = () => {
        if (!dom.recentHistoryPanel) return;
        const visible = dom.recentHistoryPanel.style.display !== 'none';
        if (visible) {
            dom.recentHistoryPanel.style.display = 'none';
            dom.recentHistoryBtn?.classList.remove('active');
            return;
        }
        renderRecentHistory();
        dom.recentHistoryPanel.style.display = 'block';
        dom.recentHistoryBtn?.classList.add('active');
    };

    const resizeInput = () => {
        if (!dom.messageInput) return;
        dom.messageInput.style.height = 'auto';
        const nextHeight = Math.min(dom.messageInput.scrollHeight, maxInputHeight);
        dom.messageInput.style.height = `${nextHeight}px`;
        dom.messageInput.style.overflowY = dom.messageInput.scrollHeight > maxInputHeight ? 'auto' : 'hidden';
    };

    const resetInput = () => {
        if (!dom.messageInput) return;
        dom.messageInput.value = '';
        dom.messageInput.style.height = '';
        dom.messageInput.style.overflowY = 'hidden';
    };

    const sendWorkbenchMessage = () => {
        const text = dom.messageInput?.value.trim();
        const connected = window.runtime?.isConnected ? window.runtime.isConnected() : false;
        if (!text || !connected) return;
        window.audioPlayer?.reset();
        if (!wsClient?.sendText(text)) return;
        store.addUserMessage(text);
        resetInput();
    };

    const copyCurrentTurn = async () => {
        const summary = store.getCurrentTurnSummary();
        if (!summary) return;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(summary);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = summary;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                textarea.remove();
            }
            window.showSubtitle?.('本轮对话已复制。', true);
        } catch (error) {
            window.showSubtitle?.(`复制失败: ${error.message || error}`, true);
        }
    };

    const clearHistory = () => {
        store.clearDisplayHistory();
        window.showSubtitle?.('已清空当前前端显示历史。', true);
    };

    const clearTrace = () => {
        traceStore?.clear?.();
        window.showSubtitle?.('运行日志已清空。', true);
        syncDetachedTraceWindow();
    };

    const copyTrace = async () => {
        const text = formatTraceForClipboard();
        if (!text) return;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                textarea.remove();
            }
            window.showSubtitle?.('运行日志已复制。', true);
        } catch (error) {
            window.showSubtitle?.(`复制日志失败: ${error.message || error}`, true);
        }
    };

    store.subscribe((messages) => {
        renderMessages(messages);
        if (dom.recentHistoryPanel?.style.display !== 'none') {
            renderRecentHistory();
        }
    });

    traceStore?.subscribe(() => {
        renderTraceEvents();
        syncDetachedTraceWindow();
    });

    ipcRenderer?.on('trace-window-ready', syncDetachedTraceWindow);
    ipcRenderer?.on('trace-window-clear-request', clearTrace);
    ipcRenderer?.on('trace-window-closed', () => {
        setTraceDetached(false);
    });

    dom.workbenchBtn?.addEventListener('click', toggleWorkbench);
    dom.closeWorkbenchBtn?.addEventListener('click', closeWorkbench);
    dom.recentHistoryBtn?.addEventListener('click', toggleRecentHistory);
    dom.closeRecentHistoryBtn?.addEventListener('click', () => {
        if (dom.recentHistoryPanel) dom.recentHistoryPanel.style.display = 'none';
        dom.recentHistoryBtn?.classList.remove('active');
    });
    dom.clearWorkbenchHistoryBtn?.addEventListener('click', clearHistory);
    dom.copyTurnBtn?.addEventListener('click', copyCurrentTurn);
    dom.clearTraceBtn?.addEventListener('click', clearTrace);
    dom.copyTraceBtn?.addEventListener('click', copyTrace);
    dom.detachTraceBtn?.addEventListener('click', openDetachedTraceWindow);
    dom.traceDebugToggle?.addEventListener('change', renderTraceEvents);
    dom.traceResizer?.addEventListener('pointerdown', startTraceResize);
    dom.sendBtn?.addEventListener('click', sendWorkbenchMessage);
    dom.messageInput?.addEventListener('input', resizeInput);
    dom.messageInput?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendWorkbenchMessage();
        }
    });

    window.workbenchUi = {
        open: openWorkbench,
        close: closeWorkbench,
        toggle: toggleWorkbench,
        getMode: () => mode
    };
})();
