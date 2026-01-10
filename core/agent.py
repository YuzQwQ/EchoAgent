from typing import Generator
from core.llm_service import LLMService
from core.vision_service import VisionService
from core.memory import MemoryManager
from core.tools.base import ToolRegistry
from core.tools.system_tools import VisionCapabilityTool, TTSCapabilityTool, MemoryCapabilityTool, SystemSelfAwarenessTool
from config import config
import random
import copy

class EchoAgent:
    def __init__(self):
        self.llm = LLMService()
        self.vision = VisionService()
        self.memory = MemoryManager()
        
        # 初始化工具注册表
        self.tools = ToolRegistry()
        self._register_core_tools()

    def _register_core_tools(self):
        """注册核心系统能力工具"""
        self.tools.register(VisionCapabilityTool())
        self.tools.register(TTSCapabilityTool())
        self.tools.register(MemoryCapabilityTool())
        self.tools.register(SystemSelfAwarenessTool())

    def _process_stream_response(self, context) -> Generator[str, None, str]:
        """
        处理流式响应，支持 <thought> 标签过滤
        返回最终的 clean response
        """
        full_raw_response = ""
        final_clean_response = ""
        buffer = ""
        is_in_thought = False
        has_started_response = False

        try:
            for chunk in self.llm.chat_stream(context):
                full_raw_response += chunk
                buffer += chunk
                
                # 1. 检测 <thought> 开始
                if "<thought>" in buffer and not is_in_thought and not has_started_response:
                    is_in_thought = True
                
                # 2. 检测 <response> 开始
                if "<response>" in buffer:
                    pre_response, post_response = buffer.split("<response>", 1)
                    
                    if is_in_thought:
                        # 打印思考过程用于调试
                        thought_content = pre_response.replace('<thought>', '').replace('</thought>', '').strip()
                        print(f"\n🧠 [Echo Thought]: {thought_content}\n")
                    
                    is_in_thought = False
                    has_started_response = True
                    buffer = post_response # 剩余 buffer 是 response 内容
                
                # 3. 处理 Response 内容
                if has_started_response:
                    # 检测 </response> 结束
                    if "</response>" in buffer:
                        content, remainder = buffer.split("</response>", 1)
                        if content:
                            yield content
                            final_clean_response += content
                        # 遇到结束标签，清空 buffer 并停止生成
                        buffer = ""
                        # break # 继续消耗流以保持连接状态，但不输出了
                    else:
                        # 没遇到结束标签，直接输出 buffer
                        yield buffer
                        final_clean_response += buffer
                        buffer = ""
                
                # 4. Fallback: 如果 buffer 过长且没有任何标签，说明模型没听话，直接输出
                elif len(buffer) > 50 and not is_in_thought:
                    print("⚠️ [Echo Logic] No tags detected, falling back to raw stream.")
                    has_started_response = True
                    yield buffer
                    final_clean_response += buffer
                    buffer = ""

            # 流结束后的清理
            if has_started_response and buffer and "</response>" not in buffer:
                yield buffer
                final_clean_response += buffer
            elif not has_started_response and buffer:
                 # 如果全程没标签，且 buffer 还有剩，输出它
                 if "<thought>" not in buffer:
                     yield buffer
                     final_clean_response += buffer

        except Exception as e:
            error_msg = f"\n\n(Error: {str(e)})"
            yield error_msg
            return error_msg

        return final_clean_response

    def _run_async_summary(self):
        """
        后台执行摘要任务
        """
        import threading
        
        def summary_task():
            self._summarize_if_needed()

        thread = threading.Thread(target=summary_task)
        thread.daemon = True # 设置为守护线程，防止阻塞主程序退出
        thread.start()

    def chat(self, user_input: str) -> Generator[str, None, None]:
        """
        处理用户输入，生成回复，并管理记忆
        """
        # 1. 保存用户输入到记忆
        self.memory.add_message("user", user_input)

        # 2. 获取上下文
        context = self.memory.get_context()

        # [新增] 注入能力认知 (Context Injection)
        # 动态获取当前工具/能力的状态描述，注入到 System Prompt 之后
        # 我们寻找 context 中第一个 system message (通常是 system prompt) 并追加内容
        # 如果没有找到，就新建一个
        capabilities_prompt = self.tools.get_capabilities_prompt()
        
        if context and context[0]["role"] == "system":
            # 追加到现有的 System Prompt
            context[0]["content"] += "\n" + capabilities_prompt
        else:
            # 插入新的 System Prompt
            context.insert(0, {"role": "system", "content": capabilities_prompt})

        # [新增] 短期逻辑强化 (Context Reinforcement)
        # 动态注入硬规则，不占用 System Prompt 长期记忆
        reinforcement_content = (
            "【逻辑守则（本次回复有效）】\n"
            "1. **一致性检查**：回顾最近 3 轮对话，禁止自我矛盾。\n"
            "2. **拒绝复读**：如果观点已表达过，请深入细节或换个角度，不要重复。\n"
            "3. **收敛话题**：除非用户发起新话题，否则请聚焦当前话题，不要无故发散。\n"
            "4. **执行 CoT**：必须先输出 <thought>，再输出 <response>。"
        )
        reinforcement_prompt = {
            "role": "system",
            "content": reinforcement_content
        }
        # 插入在倒数第一条消息（最新的 User Input）之前
        if len(context) > 0 and context[-1]["role"] == "user":
            context.insert(-1, reinforcement_prompt)
        else:
            context.append(reinforcement_prompt)

        # 3. 调用 LLM 生成回复 (使用 process_stream_response 处理 Hidden CoT)
        final_response = yield from self._process_stream_response(context)

        # 4. 保存 Echo 的回复到记忆
        if final_response:
            self.memory.add_message("assistant", final_response)
            
            # 5. 异步触发滚动摘要
            # 不阻塞当前回复生成
            self._run_async_summary()

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
        
        # 插入能力认知 (同 chat)
        capabilities_prompt = self.tools.get_capabilities_prompt()
        if context and context[0]["role"] == "system":
            context[0]["content"] += "\n" + capabilities_prompt
        else:
            context.insert(0, {"role": "system", "content": capabilities_prompt})

        # 插入逻辑强化 (同 chat)
        reinforcement_content = (
            "【视觉逻辑守则】\n"
            "1. **基于观察**：仅根据[图片内容描述]回应。\n"
            "2. **风格保持**：微毒舌、日常化、Emoji 适度。\n"
            "3. **执行 CoT**：必须先输出 <thought> 分析图片要点，再输出 <response>。"
        )
        reinforcement_prompt = {
            "role": "system",
            "content": reinforcement_content
        }
        context.insert(-1, reinforcement_prompt)

        full_response = ""
        try:
            # 使用 process_stream_response 处理 Hidden CoT
            full_response = yield from self._process_stream_response(context)
        except Exception as e:
            error_msg = f"\n\n(Error: {str(e)})"
            full_response += error_msg
            yield error_msg

        # 保存回复
        if full_response:
            self.memory.add_message("assistant", full_response)
            # 异步触发滚动摘要
            self._run_async_summary()

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
            for chunk in self._process_stream_response(context):
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
