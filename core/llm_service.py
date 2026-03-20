from openai import OpenAI, APIError
from typing import Generator, List, Dict, Any, Optional
from config import config
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from openai import RateLimitError, APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError
except Exception:
    RateLimitError = APIConnectionError = APITimeoutError = AuthenticationError = BadRequestError = APIError

class LLMService:
    def __init__(self):
        self.client = None
        if config.LLM_API_KEY:
            self.client = OpenAI(
                api_key=config.LLM_API_KEY,
                base_url=config.LLM_BASE_URL,
                timeout=config.LLM_TIMEOUT_SECONDS
            )
        self.model = config.LLM_MODEL

    def _fallback_message(self, err: Exception) -> str:
        if isinstance(err, AuthenticationError):
            return "⚠️ 模型鉴权失败，请检查 API Key。"
        if isinstance(err, RateLimitError):
            return "⚠️ 模型请求过于频繁，请稍后再试。"
        if isinstance(err, (APITimeoutError, TimeoutError)):
            return "⚠️ 模型请求超时，请稍后再试。"
        if isinstance(err, (APIConnectionError, ConnectionError)):
            return "⚠️ 模型服务连接失败，请检查网络。"
        if isinstance(err, BadRequestError):
            return "⚠️ 模型请求参数错误，请检查配置。"
        if isinstance(err, APIError):
            return "⚠️ 模型服务异常，请稍后重试。"
        return "⚠️ 模型调用失败，请稍后重试。"

    def _log_error(self, err: Exception):
        print(f"LLM Error: {type(err).__name__}: {err}")

    def chat_completion_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Any:
        """
        非流式调用，支持 Function Calling
        """
        if not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice=tool_choice if tool_choice else None,
                stream=False
            )
            return response.choices[0].message
        except Exception as e:
            self._log_error(e)
            return None

    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """
        非流式调用 LLM 生成回复
        """
        if not config.LLM_API_KEY:
             return "⚠️ 请在 .env 文件中配置 LLM_API_KEY"
        try:
            return self._chat_completion_request(messages)
        except Exception as e:
            self._log_error(e)
            return self._fallback_message(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, ConnectionError, APITimeoutError, TimeoutError)),
        reraise=True
    )
    def _chat_completion_request(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False
        )
        return response.choices[0].message.content or ""

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
            self._log_error(e)
            yield self._fallback_message(e)
