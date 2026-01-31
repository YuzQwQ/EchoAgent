from openai import OpenAI, APIError
from typing import Generator, List, Dict
from config import config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class LLMService:
    def __init__(self):
        # 初始化 OpenAI 客户端
        # 如果没有设置 API Key，这里可能会报错，但在 MVP 中我们允许启动时报错或者在调用时处理
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL
        )
        self.model = config.LLM_MODEL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, ConnectionError)),
        reraise=True
    )
    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """
        非流式调用 LLM 生成回复
        """
        if not config.LLM_API_KEY:
             return "⚠️ 请在 .env 文件中配置 LLM_API_KEY"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            # print(f"LLM API Error: {e}")
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, ConnectionError)),
        reraise=True
    )
    def chat_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """
        流式调用 LLM 生成回复
        
        Args:
            messages: 包含上下文的消息列表 [{"role": "user", "content": "..."}]
            
        Yields:
            生成的文本片段
        """
        if not config.LLM_API_KEY:
             yield "⚠️ 请在 .env 文件中配置 LLM_API_KEY"
             return

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            # 这里可以记录日志
            # print(f"LLM API Error: {e}")
            raise e
