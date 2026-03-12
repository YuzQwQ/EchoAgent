(() => {
    let nextSequenceId = 0;
    let audioBufferQueue = [];
    let isPlayingAudio = false;
    let onIdle = () => {};

    const init = ({ onIdle: onIdleCallback } = {}) => {
        if (typeof onIdleCallback === 'function') {
            onIdle = onIdleCallback;
        }
    };

    const reset = () => {
        if (isPlayingAudio) {
            window.lipSync?.stop();
        }
        audioBufferQueue = [];
        nextSequenceId = 0;
        isPlayingAudio = false;
    };

    const handleStream = (data) => {
        const { sequence_id, content } = data;
        audioBufferQueue.push({ id: sequence_id, content: content });
        audioBufferQueue.sort((a, b) => a.id - b.id);
        tryPlayNext();
    };

    const tryPlayNext = () => {
        if (isPlayingAudio) return;

        if (audioBufferQueue.length === 0) {
            onIdle();
            return;
        }

        const nextItem = audioBufferQueue[0];
        if (nextItem.id !== nextSequenceId) {
            console.log(`Waiting for sequence ${nextSequenceId}, but got ${nextItem.id} (buffered: ${audioBufferQueue.length})`);
            return;
        }

        audioBufferQueue.shift();
        nextSequenceId++;
        playAudioStream(nextItem.content);
    };

    const playAudioStream = (base64Data) => {
        isPlayingAudio = true;
        const audio = new Audio('data:audio/wav;base64,' + base64Data);

        audio.onended = () => {
            isPlayingAudio = false;
            window.lipSync?.stop();
            tryPlayNext();
        };

        audio.onerror = (e) => {
            console.error('Audio playback error', e);
            isPlayingAudio = false;
            window.lipSync?.stop();
            tryPlayNext();
        };

        audio.play().then(() => {
            window.lipSync?.start(audio);
        }).catch(e => {
            console.error('Auto-play prevented', e);
            isPlayingAudio = false;
            tryPlayNext();
        });
    };

    const queueSingle = (base64Data) => {
        reset();
        handleStream({ sequence_id: 0, content: base64Data });
    };

    const isPlaying = () => isPlayingAudio;
    const isQueueEmpty = () => audioBufferQueue.length === 0;

    window.audioPlayer = {
        init,
        reset,
        handleStream,
        queueSingle,
        isPlaying,
        isQueueEmpty
    };
})();
