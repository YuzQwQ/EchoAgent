(() => {
    const subtitleBar = window.dom?.subtitleBar;
    let subtitleTimer = null;

    class Typewriter {
        constructor() {
            this.queue = [];
            this.isTyping = false;
            this.currentText = '';
            this.typingSpeed = 42;
            this.timer = null;
        }

        append(text) {
            for (let char of text) {
                if (this.currentText === '' && this.queue.length === 0 && char.trim() === '') {
                    continue;
                }
                this.queue.push(char);
            }
            if (!this.isTyping) {
                this.processQueue();
            }
        }

        processQueue() {
            if (this.queue.length === 0) {
                this.isTyping = false;
                const readDuration = 3000 + this.currentText.length * 150;
                this.setHideTimeout(readDuration);
                return;
            }

            this.isTyping = true;
            subtitleBar.classList.remove('hide');
            subtitleBar.classList.add('show');
            if (subtitleTimer) clearTimeout(subtitleTimer);

            const char = this.queue.shift();
            this.currentText += char;
            subtitleBar.innerText = this.currentText;

            let delay = this.typingSpeed;
            if (['，', ',', '。', '.', '！', '!', '？', '?', '；', ';', '、'].includes(char)) {
                delay = 180;
            }

            this.timer = setTimeout(() => this.processQueue(), delay);
        }

        clear() {
            this.queue = [];
            this.currentText = '';
            this.isTyping = false;
            subtitleBar.innerText = '';
            if (this.timer) clearTimeout(this.timer);
        }

        setHideTimeout(duration) {
            if (subtitleTimer) clearTimeout(subtitleTimer);
            subtitleTimer = setTimeout(() => {
                subtitleBar.classList.remove('show');
                subtitleBar.classList.add('hide');
            }, duration);
        }
    }

    const subtitleTypewriter = new Typewriter();
    const chatContainer = window.dom?.chatContainer;
    let isEchoActive = false;

    const showSubtitle = (text, autoHide = true) => {
        if (!subtitleBar) return;
        if (text.startsWith('🎤') || text.startsWith('[系统]')) {
            subtitleTypewriter.clear();
        }

        subtitleBar.innerText = text;
        subtitleBar.classList.remove('hide');
        subtitleBar.classList.add('show');

        if (subtitleTimer) clearTimeout(subtitleTimer);

        if (autoHide) {
            const duration = Math.max(3000, text.length * 200);
            subtitleTimer = setTimeout(() => {
                subtitleBar.classList.remove('show');
                subtitleBar.classList.add('hide');
            }, duration);
        }
    };

    const showBubble = (text, duration) => {
        showSubtitle(text, duration > 0);
    };

    const scrollToBottom = () => {
        if (!chatContainer) return;
        chatContainer.scrollTop = chatContainer.scrollHeight;
    };

    const handleUserInput = (content) => {
        showSubtitle(`🎤 ${content}`, true);
    };

    const handleChunkStart = () => {
        isEchoActive = true;
        subtitleTypewriter.clear();
        showSubtitle('', false);
    };

    const handleChunkText = (text) => {
        subtitleTypewriter.append(text);
    };

    const handleChunkDone = () => {
        isEchoActive = false;
        const audioPlayer = window.audioPlayer;
        if (audioPlayer && !audioPlayer.isPlaying() && audioPlayer.isQueueEmpty()) {
            subtitleTypewriter.setHideTimeout(3000);
        }
    };

    const handleError = (content) => {
        showSubtitle(`Error: ${content}`, true);
        isEchoActive = false;
    };

    const handleAudioIdle = () => {
        if (!isEchoActive) {
            subtitleTypewriter.setHideTimeout(3000);
        }
    };

    window.subtitleTypewriter = subtitleTypewriter;
    window.showSubtitle = showSubtitle;
    window.showBubble = showBubble;
    window.renderHelpers = {
        scrollToBottom,
        handleUserInput,
        handleChunkStart,
        handleChunkText,
        handleChunkDone,
        handleError,
        handleAudioIdle
    };
})();
