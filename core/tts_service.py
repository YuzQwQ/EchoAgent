import base64
import edge_tts
import httpx
from config import config
from tenacity import retry, stop_after_attempt, wait_exponential

class TTSService:
    def __init__(self):
        self.provider = config.TTS_PROVIDER
        
        if self.provider == "gpt-sovits":
            self.gpt_sovits_url = config.GPT_SOVITS_URL
            print(f"TTS Service Initialized (Provider: GPT-SoVITS, URL: {self.gpt_sovits_url})")
        else:
            # Default to Edge TTS
            self.edge_voice = config.EDGE_TTS_VOICE
            print(f"TTS Service Initialized (Provider: Edge TTS, Voice: {self.edge_voice})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def _generate_audio_edge_with_retry(self, text: str):
        communicate = edge_tts.Communicate(text, self.edge_voice)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def _generate_audio_gpt_sovits_with_retry(self, text: str):
        async with httpx.AsyncClient() as client:
            payload = {
                "text": text,
                "text_lang": "zh"
            }
            # GPT-SoVITS 可能需要较长的生成时间，设置较长的 timeout
            response = await client.post(self.gpt_sovits_url, json=payload, timeout=60.0)
            response.raise_for_status()
            return response.content

    async def text_to_speech(self, text: str):
        """
        生成语音，返回 Base64 编码的音频数据
        """
        try:
            if self.provider == "gpt-sovits":
                audio_bytes = await self._generate_audio_gpt_sovits_with_retry(text)
            else:
                audio_bytes = await self._generate_audio_edge_with_retry(text)
                
            return base64.b64encode(audio_bytes).decode('utf-8')
            
        except Exception as e:
            print(f"Error generating speech ({self.provider}) after retries: {e}")
            # 如果 GPT-SoVITS 失败，是否要回退到 Edge TTS？
            # 暂时不回退，直接返回 None，让前端处理或静音
            return None
