from openai import OpenAI, APIError
from typing import Generator, List, Dict, Any, Optional
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
            # [Fix] 显式定义工具集，避免 LLM 不知道有工具可用
            # 这里我们假设 messages 里没有 tool_choice，如果需要强制调用工具，需要在外层处理
            # 但对于 chat_stream，我们希望它既能聊天也能调用工具
            # 目前 EchoAgent 并没有把 tools 传递给 chat_stream，这是问题所在！
            
            # 临时方案：如果 messages 里包含了 tool 相关的信息（目前没有），或者我们希望它自动调用工具
            # 但这里 chat_stream 是纯文本生成。
            # 要支持 Tool Call，我们需要：
            # 1. 传递 tools 定义给 LLM
            # 2. 处理 LLM 返回的 tool_calls
            # 3. 执行工具
            # 4. 把结果喂回 LLM
            
            # 目前 Echo 的架构是：
            # User -> Agent.chat -> Agent._build_context -> LLM.chat_stream
            # Agent 本身并没有实现 ReAct 循环或 Function Calling 循环。
            # 这就是为什么它会“编造”结果 —— 它根本没去调工具！
            
            # 修复计划：
            # 1. 修改 chat_stream 签名，允许传入 tools
            # 2. 在 Agent.chat 里，先进行一轮非流式的 Tool Call 检查
            # 3. 如果有 Tool Call，执行之，把结果加入 context，再进行最终的流式生成
            
            # 但为了最小化改动，我们先只修改 Agent.chat 逻辑，让它支持 Function Calling。
            # 而 llm_service.chat_completion 已经支持了吗？没有。
            
            # 我们先给 LLMService 加一个 chat_completion_with_tools 方法
            pass 

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
