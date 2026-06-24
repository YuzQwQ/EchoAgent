(() => {
    const { ipcRenderer } = window.require ? window.require('electron') : { ipcRenderer: null };
    const traceList = document.getElementById('trace-list');
    const debugToggle = document.getElementById('debug-toggle');
    const copyBtn = document.getElementById('copy-btn');
    const clearBtn = document.getElementById('clear-btn');

    let events = [];

    const escapeHtml = (value) => String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const formatTime = (timestamp) => {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleTimeString([], { hour12: false });
    };

    const visibleEvents = () => {
        const showDebug = Boolean(debugToggle?.checked);
        return events.filter((event) => showDebug || event.level !== 'debug');
    };

    const detailsFor = (event) => {
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

    const render = () => {
        if (!traceList) return;
        const rows = visibleEvents();
        if (!rows.length) {
            traceList.innerHTML = '<div class="trace-empty">No runtime logs.</div>';
            return;
        }

        traceList.innerHTML = rows.map((event) => {
            const level = event.level || 'info';
            const detail = detailsFor(event);
            const preview = event.content_preview ? `<div class="trace-preview">${escapeHtml(event.content_preview)}</div>` : '';
            return `
                <div class="trace-row ${escapeHtml(level)}">
                    <span class="trace-time">${escapeHtml(formatTime(event.timestamp))}</span>
                    <span class="trace-level">${escapeHtml(level)}</span>
                    <span class="trace-event">${escapeHtml(event.event || 'event')}</span>
                    <span class="trace-message">${escapeHtml(event.message || '')}</span>
                    ${detail ? `<span class="trace-detail">${escapeHtml(detail)}</span>` : ''}
                    ${preview}
                </div>
            `;
        }).join('');
        traceList.scrollTop = traceList.scrollHeight;
    };

    const formatForClipboard = () => {
        return visibleEvents().map((event) => {
            const detail = detailsFor(event);
            const parts = [
                `[${formatTime(event.timestamp)}]`,
                `[${event.level || 'info'}]`,
                event.event || 'event',
                event.message || ''
            ];
            if (detail) parts.push(detail);
            if (event.content_preview) parts.push(`preview=${event.content_preview}`);
            return parts.filter(Boolean).join(' ');
        }).join('\n');
    };

    const copyLogs = async () => {
        const text = formatForClipboard();
        if (!text) return;
        try {
            await navigator.clipboard.writeText(text);
        } catch (error) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            textarea.remove();
        }
    };

    ipcRenderer?.on('trace-events', (event, payload) => {
        events = Array.isArray(payload?.events) ? payload.events : [];
        render();
    });

    debugToggle?.addEventListener('change', render);
    copyBtn?.addEventListener('click', copyLogs);
    clearBtn?.addEventListener('click', () => {
        ipcRenderer?.send('trace-window-clear-request');
    });

    ipcRenderer?.send('trace-window-ready');
    render();
})();
