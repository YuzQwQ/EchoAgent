from typing import Generator
from core.llm_service import LLMService
from core.vision_service import VisionService
from core.memory import MemoryManager
from config import config
import random
import copy

class EchoAgent:
    def __init__(self):
        self.llm = LLMService()
        self.vision = VisionService()
        self.memory = MemoryManager()

    def chat(self, user_input: str) -> Generator[str, None, None]:
        """
        处理用户输入，生成回复，并管理记忆
        """
        # 1. 保存用户输入到记忆
        self.memory.add_message("user", user_input)

        # 2. 获取上下文
        context = self.memory.get_context()

        # [新增] 短期逻辑强化 (Context Reinforcement)
        # 在 System Prompt 和 History 之后，User Input 之前，插入逻辑约束
        # 利用 Recency Bias 强制模型关注短期一致性和收敛性
        reinforcement_prompt = {
            "role": "system",
            "content": "【逻辑守则】\n1. 请回顾最近 3 轮对话，确保你的回复与之前的陈述保持绝对逻辑一致，禁止“吃书”或自我矛盾。\n2. 如果用户在追问细节，请务必“收敛”话题，提供更深层的具体信息，严禁重复已说过的笼统观点。\n3. 保持人设的连贯性。"
        }
        # 插入在倒数第一条消息（最新的 User Input）之前
        if len(context) > 0 and context[-1]["role"] == "user":
            context.insert(-1, reinforcement_prompt)
        else:
            context.append(reinforcement_prompt)

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
            
            # 5. 检查是否需要触发滚动摘要
            # 这里的逻辑是同步执行的，可能会导致最后输出完稍微卡一下
            # 但能保证下一次对话时 memory 是干净的
            self._summarize_if_needed()

    def process_image(self, image_data: bytes, mime_type: str = "image/jpeg") -> Generator[str, None, None]:
        """
        处理图片输入：
        1. 调用 Vision Service 识别图片
        2. 将识别结果注入上下文
        3. 让 Echo 基于识别结果生成回复
        """
        yield "👀 正在观察图片..."
        
        # 1. 识别图片
        description = self.vision.analyze_image(image_data, mime_type)
        
        if "失败" in description:
            yield f"\n\n看不清这张图... ({description})"
            return

        yield "\n\n🤔 嗯..." # 模拟思考

        # 2. 构造上下文消息
        # 格式：【视觉观察】用户发送了一张图片。内容描述：...
        observation_msg = f"【视觉观察】用户发送了一张图片。\n[图片内容描述]: {description}"
        
        # 3. 存入记忆 (作为 System 消息或特殊的 User 消息)
        # 这里为了让 LLM 觉得是用户发的图，我们用 user role，但加标注
        self.memory.add_message("user", observation_msg)
        
        # 4. 触发回复生成 (就像用户发了文字一样)
        # 获取上下文
        context = self.memory.get_context()
        
        # 插入逻辑强化 (同 chat)
        reinforcement_prompt = {
            "role": "system",
            "content": "【逻辑守则】\n1. 用户刚发了一张图片，请根据[图片内容描述]进行回应。\n2. 保持日常、微毒舌风格。如果图片很有趣，可以吐槽；如果是清单，可以确认。"
        }
        context.insert(-1, reinforcement_prompt)

        full_response = ""
        try:
            for chunk in self.llm.chat_stream(context):
                full_response += chunk
                yield chunk
        except Exception as e:
            error_msg = f"\n\n(Error: {str(e)})"
            full_response += error_msg
            yield error_msg

        # 保存回复
        if full_response:
            self.memory.add_message("assistant", full_response)
            self._summarize_if_needed()

    def _summarize_if_needed(self):
        """
        检查历史记录长度，如果超长，则触发摘要压缩
        """
        history = self.memory.load_history()
        # 阈值：保留最近 MAX_HISTORY_ROUNDS 轮（*2 条消息）
        # 如果超过阈值 + 2（至少多出一轮），就开始压缩最早的一轮
        max_msgs = config.MAX_HISTORY_ROUNDS * 2
        
        if len(history) > max_msgs:
            # 取出最早的一轮对话（通常是 User + Assistant）
            # 注意：pop_oldest_messages 会直接从 memory 中移除它们
            # 所以我们要确保摘要生成成功后再保存，或者接受短暂的数据风险
            # 这里简单起见，先 pop 出来，再生成摘要
            
            # 我们一次性压缩多一点，避免频繁触发？
            # 还是每次只压缩 2 条？为了平滑，每次压缩 2 条比较稳
            old_messages = self.memory.pop_oldest_messages(2)
            if not old_messages:
                return

            current_summary = self.memory.get_summary()
            
            # 构造摘要 Prompt
            # 这是一个后台任务，不需要太复杂的 System Prompt，只要指令清晰
            summary_prompt = [
                {"role": "system", "content": "你是一个对话摘要助手。你的任务是将新的对话内容合并到现有的摘要中。保留关键事实、用户偏好和当前状态。忽略寒暄和废话。"},
                {"role": "user", "content": f"""
请更新以下对话摘要。

【旧摘要】：{current_summary or "无"}

【新增对话】：
{old_messages[0]['role']}: {old_messages[0]['content']}
{old_messages[1]['role'] if len(old_messages)>1 else ''}: {old_messages[1]['content'] if len(old_messages)>1 else ''}

【要求】：
1. 输出更新后的摘要，保持简练。
2. 使用第三人称（如“用户说...”，“AI回复...”）。
3. 如果新增对话没有实质信息（如单纯的问候），可以保留旧摘要不变。
"""}
            ]
            
            try:
                # 非流式调用
                new_summary = ""
                for chunk in self.llm.chat_stream(summary_prompt):
                    new_summary += chunk
                
                # 更新 Memory
                if new_summary.strip():
                    self.memory.update_summary(new_summary.strip())
                    # print(f"Summary updated: {new_summary}") # Debug log
                    
            except Exception as e:
                print(f"Summary generation failed: {e}")
                # 如果失败，消息已经 pop 掉了，这部分记忆丢失。
                # 生产环境应该先 peek 再 pop，或者有回滚机制。
                # MVP 阶段暂且接受。

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
