(() => {
    const maxEvents = 500;
    let events = [];
    const listeners = new Set();

    const clone = (items) => items.map((item) => ({ ...item }));

    const notify = () => {
        const snapshot = clone(events);
        listeners.forEach((listener) => listener(snapshot));
    };

    const addEvent = (event) => {
        if (!event || typeof event !== 'object') return null;
        const normalized = {
            id: event.id || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            type: 'trace_event',
            level: event.level || 'info',
            event: event.event || 'event',
            timestamp: event.timestamp || new Date().toISOString(),
            message: event.message || '',
            ...event
        };
        events.push(normalized);
        if (events.length > maxEvents) {
            events = events.slice(events.length - maxEvents);
        }
        notify();
        return normalized;
    };

    const clear = () => {
        events = [];
        notify();
    };

    const getEvents = () => clone(events);

    const subscribe = (listener) => {
        if (typeof listener !== 'function') {
            return () => {};
        }
        listeners.add(listener);
        listener(clone(events));
        return () => listeners.delete(listener);
    };

    window.traceStore = {
        addEvent,
        clear,
        getEvents,
        subscribe
    };
})();
