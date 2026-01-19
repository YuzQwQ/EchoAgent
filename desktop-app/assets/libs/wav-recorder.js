// 简单的 WAV 录音器
class WavRecorder {
    constructor() {
        this.mediaStream = null;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.processor = null;
        this.audioInput = null;
        this.chunks = [];
        this.recording = false;
    }

    async start() {
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.audioInput = this.audioContext.createMediaStreamSource(this.mediaStream);
            
            // 使用 ScriptProcessorNode 处理音频数据 (deprecated but widely supported)
            // 缓冲区大小 4096, 1 输入通道, 1 输出通道
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            let sampleRate = this.audioContext.sampleRate;
            this.chunks = [];
            
            this.processor.onaudioprocess = (e) => {
                if (!this.recording) return;
                const inputData = e.inputBuffer.getChannelData(0);
                // 克隆数据，因为 inputData 会被重用
                this.chunks.push(new Float32Array(inputData));
            };
            
            this.audioInput.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            this.recording = true;
            return true;
        } catch (e) {
            console.error("WavRecorder start error:", e);
            throw e;
        }
    }

    async stop() {
        this.recording = false;
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }
        
        if (this.audioInput) this.audioInput.disconnect();
        if (this.processor) this.processor.disconnect();
        if (this.audioContext) await this.audioContext.close();
        
        // 合并所有 buffer
        let length = 0;
        this.chunks.forEach(chunk => length += chunk.length);
        let buffer = new Float32Array(length);
        let offset = 0;
        this.chunks.forEach(chunk => {
            buffer.set(chunk, offset);
            offset += chunk.length;
        });
        
        // 降采样到 16000Hz (可选，Google Speech API 偏好 16k 或 44.1k，但减少数据量更好)
        // 这里为了简单，保持原始采样率 (通常是 44100 或 48000)
        // 转换为 16-bit PCM WAV
        return this.encodeWAV(buffer, this.audioContext.sampleRate);
    }

    encodeWAV(samples, sampleRate) {
        let buffer = new ArrayBuffer(44 + samples.length * 2);
        let view = new DataView(buffer);

        /* RIFF identifier */
        this.writeString(view, 0, 'RIFF');
        /* RIFF chunk length */
        view.setUint32(4, 36 + samples.length * 2, true);
        /* RIFF type */
        this.writeString(view, 8, 'WAVE');
        /* format chunk identifier */
        this.writeString(view, 12, 'fmt ');
        /* format chunk length */
        view.setUint32(16, 16, true);
        /* sample format (raw) */
        view.setUint16(20, 1, true);
        /* channel count */
        view.setUint16(22, 1, true);
        /* sample rate */
        view.setUint32(24, sampleRate, true);
        /* byte rate (sample rate * block align) */
        view.setUint32(28, sampleRate * 2, true);
        /* block align (channel count * bytes per sample) */
        view.setUint16(32, 2, true);
        /* bits per sample */
        view.setUint16(34, 16, true);
        /* data chunk identifier */
        this.writeString(view, 36, 'data');
        /* data chunk length */
        view.setUint32(40, samples.length * 2, true);

        this.floatTo16BitPCM(view, 44, samples);

        return new Blob([view], { type: 'audio/wav' });
    }

    floatTo16BitPCM(output, offset, input) {
        for (let i = 0; i < input.length; i++, offset += 2) {
            let s = Math.max(-1, Math.min(1, input[i]));
            output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }
    }

    writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }
}
