from openai import OpenAI, APIError
from typing import Generator, List, Dict, Any, Optional
from config import config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL
        )
        self.model = config.LLM_MODEL

    def chat_completion_with_tools(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """
        非流式调用，支持 Function Calling
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
                stream=False
            )
            return response.choices[0].message
        except Exception as e:
            print(f"LLM Tool Call Error: {e}")
            return None

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
    def chat_stream(self, messages: List[Dict[str, str]], trace_id: Optional[str] = None) -> Generator[str, None, None]:
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
            import time
            start = time.monotonic()
            if trace_id:
                print(f"[trace:{trace_id}] llm_stream_start model={self.model} messages={len(messages)}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
            if trace_id:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                print(f"[trace:{trace_id}] llm_stream_end elapsed_ms={elapsed_ms}")

        except Exception as e:
            if trace_id:
                print(f"[trace:{trace_id}] llm_stream_error error={str(e)}")
            raise e
