from typing import Generator
from core.llm_service import LLMService
from core.memory import MemoryManager
import random
import copy

class EchoAgent:
    def __init__(self):
        self.llm = LLMService()
        self.memory = MemoryManager()

    def chat(self, user_input: str) -> Generator[str, None, None]:
        """
        处理用户输入，生成回复，并管理记忆
        """
        # 1. 保存用户输入到记忆
        self.memory.add_message("user", user_input)

        # 2. 获取上下文
        context = self.memory.get_context()

        # 3. 调用 LLM 生成回复
        full_response = ""
        try:
            for chunk in self.llm.chat_stream(context):
                full_response += chunk
                yield chunk
        except Exception as e:
            error_msg = f"\n\n(Error: {str(e)})"
            full_response += error_msg
            yield error_msg

        # 4. 保存 Echo 的回复到记忆
        if full_response:
            self.memory.add_message("assistant", full_response)

    def proactive_chat(self) -> Generator[str, None, None]:
        """
        主动发言逻辑：检测是否需要追加发言
        """
        history = self.memory.load_history()
        if not history or history[-1]["role"] != "assistant":
            return 

        # 构造 Context：
        original_context = self.memory.get_context()
        context = copy.deepcopy(original_context)
        
        # 新的 Instruction：简化指令，避免模型过度演绎
        # 使用 system role 追加在末尾（如果模型支持），或者作为 user 消息
        # 为了通用性，这里作为 user 消息，但明确是系统指令
        instruction = (
            "（系统指令：基于你的人设，如果你觉得刚才的话意犹未尽，可以追加一句简短的补充或吐槽。请直接输出内容，不要包含动作描写。如果没有要补充的，回复 PASS。）"
        )
        
        context.append({"role": "user", "content": instruction})

        full_response = ""
        try:
            for chunk in self.llm.chat_stream(context):
                full_response += chunk
            
            clean_response = full_response.strip()
            
            # 严格判断 PASS
            if "PASS" in clean_response.upper() or len(clean_response) < 2:
                return
            
            # 过滤掉明显的非对话内容（比如模型输出了“思考中...”或者动作描写）
            if clean_response.startswith("（") and clean_response.endswith("）") and len(clean_response) > 10:
                 # 这种通常是单纯的动作描写，过滤掉
                 pass
            
            self.memory.add_message("assistant", clean_response)
            yield clean_response

        except Exception as e:
            print(f"Proactive chat error: {e}")
            return
    
    def get_history(self):
        return self.memory.load_history()

    def clear_memory(self):
        self.memory.clear_history()
