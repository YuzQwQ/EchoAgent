import base64
import edge_tts
from config import config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class TTSService:
    def __init__(self):
        # Edge TTS Init
        self.edge_voice = config.EDGE_TTS_VOICE
        print(f"TTS Service Initialized (Provider: Edge TTS, Voice: {self.edge_voice})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def _generate_audio_with_retry(self, text: str):
        communicate = edge_tts.Communicate(text, self.edge_voice)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    async def text_to_speech(self, text: str):
        """
        生成语音，返回 Base64 编码的音频数据
        """
        try:
            # 调用带重试机制的内部方法
            audio_bytes = await self._generate_audio_with_retry(text)
            return base64.b64encode(audio_bytes).decode('utf-8')
            
        except Exception as e:
            print(f"Error generating speech (Edge TTS) after retries: {e}")
            return None
