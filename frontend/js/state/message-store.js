(() => {
    let messages = [];
    let activeAssistantId = null;
    let nextId = 1;
    const subscribers = new Set();

    const now = () => new Date().toISOString();

    const cloneMessage = (message) => ({ ...message });

    const notify = () => {
        const snapshot = messages.map(cloneMessage);
        subscribers.forEach((listener) => {
            try {
                listener(snapshot);
            } catch (error) {
                console.warn('MessageStore subscriber failed:', error);
            }
        });
    };

    const addMessage = (role, content, extra = {}) => {
        const message = {
            id: `m_${nextId++}`,
            role,
            content: content || '',
            createdAt: now(),
            ...extra
        };
        messages.push(message);
        notify();
        return message;
    };

    const addUserMessage = (content) => {
        activeAssistantId = null;
        return addMessage('user', content);
    };

    const startAssistantMessage = () => {
        const message = addMessage('assistant', '', { streaming: true });
        activeAssistantId = message.id;
        return message;
    };

    const appendAssistantChunk = (text) => {
        if (!activeAssistantId) {
            startAssistantMessage();
        }
        const message = messages.find((item) => item.id === activeAssistantId);
        if (!message) {
            activeAssistantId = null;
            return appendAssistantChunk(text);
        }
        message.content += text || '';
        notify();
        return message;
    };

    const finishAssistantMessage = () => {
        if (!activeAssistantId) return null;
        const message = messages.find((item) => item.id === activeAssistantId);
        if (message) {
            message.streaming = false;
        }
        activeAssistantId = null;
        notify();
        return message || null;
    };

    const addSystemMessage = (content) => addMessage('system', content);

    const clearDisplayHistory = () => {
        messages = [];
        activeAssistantId = null;
        notify();
    };

    const getMessages = () => messages.map(cloneMessage);

    const getRecentMessages = (limit = 10) => {
        const count = Math.max(0, Number(limit) || 0);
        return messages.slice(-count).map(cloneMessage);
    };

    const getCurrentTurnSummary = () => {
        const lastUserIndex = messages.map((message) => message.role).lastIndexOf('user');
        const turn = lastUserIndex >= 0 ? messages.slice(lastUserIndex) : messages.slice(-1);
        return turn
            .filter((message) => message.content && message.content.trim())
            .map((message) => {
                const label = message.role === 'user'
                    ? 'User'
                    : message.role === 'assistant'
                        ? 'Echo'
                        : 'System';
                return `${label}: ${message.content.trim()}`;
            })
            .join('\n\n');
    };

    const subscribe = (listener) => {
        if (typeof listener !== 'function') {
            return () => {};
        }
        subscribers.add(listener);
        listener(getMessages());
        return () => subscribers.delete(listener);
    };

    window.messageStore = {
        addUserMessage,
        startAssistantMessage,
        appendAssistantChunk,
        finishAssistantMessage,
        addSystemMessage,
        clearDisplayHistory,
        getMessages,
        getRecentMessages,
        getCurrentTurnSummary,
        subscribe
    };
})();
