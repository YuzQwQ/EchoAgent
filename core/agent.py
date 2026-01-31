from typing import Generator
from datetime import datetime
from core.llm_service import LLMService
from core.vision_service import VisionService
from core.memory import MemoryManager
from core.rag_service import RAGService
from core.tools.base import ToolRegistry
from core.tools.system_tools import (
    VisionCapabilityTool, 
    TTSCapabilityTool, 
    MemoryCapabilityTool, 
    SystemSelfAwarenessTool,
    ProjectHistoryTool
)
from config import config
import random
import copy

class EchoAgent:
    def __init__(self):
        self.llm = LLMService()
        self.vision = VisionService()
        self.memory = MemoryManager()
        try:
            self.rag = RAGService(knowledge_name="terraria")
        except Exception as e:
            print(f"Warning: RAG Service failed to initialize: {e}")
            self.rag = None
            
        self.l0_max_items = 60
        self.l0_aggregate_size = 4
        self.l1_max_items = 20
        self.l2_max_items = 50
        self.ref_cooldown_turns = 3
        
        # 初始化工具注册表
        self.tools = ToolRegistry()
        self._register_core_tools()

    def _register_core_tools(self):
        """注册核心系统能力工具"""
        self.tools.register(VisionCapabilityTool())
        self.tools.register(TTSCapabilityTool())
        self.tools.register(MemoryCapabilityTool())
        self.tools.register(SystemSelfAwarenessTool())
        self.tools.register(ProjectHistoryTool())

    def add_observation_to_context(self, observation: str):
        """
        将观察到的事件添加到短期记忆 (Context) 中，但不触发回复。
        这让 Echo 拥有“上帝视角”，知道用户刚才干了什么。
        """
        # 使用 MemoryCapabilityTool 或直接操作 memory
        # 这里为了简单，直接作为一条 System Message 或 User Info 插入
        # 但我们不想让它变成 "User said: ...", 而是 "System noticed: ..."
        
        # 我们可以把它包装成一条特殊的 System Message，或者 append 到 chat history
        # 但为了不污染对话历史，最好放在 System Prompt 的 dynamic context 里
        # 目前最简单的方法是作为一条 "Hidden User Message" 插入，但标记为已处理
        
        # 更好的方案：
        # 在下一次用户说话时，把这个观察结果作为 Context 附带进去。
        # 这里我们先存到一个临时的 buffer 里
        
        # 暂时利用 memory 模块的 add_short_term_memory (如果存在)
        # 或者直接存入 self.memory
        
        # [Hack] 既然我们已经有了 Context Reinforcement 机制，
        # 我们可以把这个观察结果存入 self.memory 的一个特殊字段
        # 下次 _build_context 时取出来。
        
        # 这里简单打印，实际需要 MemoryManager 支持 short_term_observation
        # 假设 MemoryManager 有这个接口 (如果没有，我们需要加，或者暂时不存)
        entry = {
            "id": self._make_id("l0"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "description": observation
        }
        self.memory.add_l0_observation(entry, max_items=self.l0_max_items)
        self._aggregate_l0_to_l1_if_needed()
        print(f"🧠 [Memory] Recorded observation: {entry}")

    def _make_id(self, prefix: str) -> str:
        return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

    def _aggregate_l0_to_l1_if_needed(self):
        l0_items = self.memory.get_l0()
        if len(l0_items) < self.l0_aggregate_size:
            return
        recent = l0_items[-self.l0_aggregate_size:]
        fragment = self._build_l1_fragment(recent)
        if fragment:
            self.memory.add_l1_fragment(fragment, max_items=self.l1_max_items)
            self.memory.pop_l0_tail(self.l0_aggregate_size)

    def _build_l1_fragment(self, entries: list) -> dict:
        texts = [e.get("description", "") for e in entries if e.get("description")]
        if not texts:
            return {}
        combined = "；".join(texts)
        activity, note = self._split_activity_note(combined)
        if not note and len(texts) > 1:
            note = "；".join(texts[1:])
        mood_guess = self._guess_mood(combined)
        return {
            "id": self._make_id("l1"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "activity": activity,
            "mood_guess": mood_guess,
            "note": note,
            "source_ids": [e.get("id") for e in entries if e.get("id")]
        }

    def _split_activity_note(self, observation: str):
        if not observation:
            return "", ""
        import re
        parts = re.split(r'[。！？!?；;，,\n]', observation, maxsplit=1)
        activity = parts[0].strip()
        note = parts[1].strip() if len(parts) > 1 else ""
        return activity, note

    def _guess_mood(self, observation: str) -> str:
        text = (observation or "").lower()
        if any(k in text for k in ["开心", "兴奋", "得意", "高兴", "胜利", "happy"]):
            return "开心"
        if any(k in text for k in ["难过", "低落", "失落", "沮丧", "sad", "哭"]):
            return "难过"
        if any(k in text for k in ["生气", "愤怒", "不爽", "烦", "angry"]):
            return "生气"
        if any(k in text for k in ["惊讶", "震惊", "surprise", "突然"]):
            return "惊讶"
        if any(k in text for k in ["专注", "认真", "写代码", "coding", "debug", "工作", "学习"]):
            return "专注"
        if any(k in text for k in ["放松", "休闲", "刷", "看视频", "relax"]):
            return "放松"
        return "平静"

    def _tokenize(self, text: str):
        import re
        if not text:
            return []
        tokens = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        tokens += re.findall(r'[a-zA-Z0-9]{2,}', text.lower())
        return list(dict.fromkeys(tokens))

    def _select_relevant_from_layer(self, items: list, query: str, current_turn: int):
        if not items:
            return None
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return None
        cooldown = self.memory.get_cooldown()
        last_ref_id = cooldown.get("last_ref_id", "")
        last_ref_turn = cooldown.get("last_ref_turn", 0)
        best = None
        best_score = 0
        for item in reversed(items):
            item_id = item.get("id", "")
            if item_id and item_id == last_ref_id and current_turn - last_ref_turn < self.ref_cooldown_turns:
                continue
            text = f"{item.get('activity', '')} {item.get('note', '')} {item.get('event', '')}"
            tokens = self._tokenize(text)
            if not tokens:
                continue
            score = len(set(query_tokens) & set(tokens))
            if score > best_score:
                best_score = score
                best = item
        if best_score == 0:
            return None
        return best

    def _select_relevant_from_l0(self, query: str, current_turn: int):
        l0_items = self.memory.get_l0()
        if not l0_items:
            return None
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return None
        cooldown = self.memory.get_cooldown()
        last_ref_id = cooldown.get("last_ref_id", "")
        last_ref_turn = cooldown.get("last_ref_turn", 0)
        best = None
        best_score = 0
        for item in reversed(l0_items):
            item_id = item.get("id", "")
            if item_id and item_id == last_ref_id and current_turn - last_ref_turn < self.ref_cooldown_turns:
                continue
            text = item.get("description", "")
            tokens = self._tokenize(text)
            if not tokens:
                continue
            score = len(set(query_tokens) & set(tokens))
            if score > best_score:
                best_score = score
                best = item
        if best_score == 0:
            return None
        return best

    def _build_layered_memory_prompt(self, query: str, allow: bool, allow_l0: bool = False):
        if not allow:
            return None
        current_turn = self.memory.get_turn()
        l1_items = self.memory.get_l1()
        l2_items = self.memory.get_l2()
        selected = self._select_relevant_from_layer(l1_items, query, current_turn)
        if not selected:
            selected = self._select_relevant_from_layer(l2_items, query, current_turn)
        if not selected and allow_l0:
            selected = self._select_relevant_from_l0(query, current_turn)
        if not selected:
            return None
        selected_id = selected.get("id", "")
        if selected_id:
            self.memory.update_cooldown(selected_id, current_turn)
        if "event" in selected:
            time_str = selected.get("time", "")
            event = selected.get("event", "")
            status = selected.get("status", "")
            return f"【上下文记忆】仅供本次回复参考，若不相关请忽略。time: {time_str} | event: {event} | status: {status}"
        if "description" in selected:
            time_str = selected.get("time", "")
            desc = selected.get("description", "")
            return f"【观察记忆】仅供本次回复参考，若不相关请忽略。time: {time_str} | description: {desc}"
        time_str = selected.get("time", "")
        activity = selected.get("activity", "")
        mood = selected.get("mood_guess", "")
        note = selected.get("note", "")
        return f"【行为片段记忆】仅供本次回复参考，若不相关请忽略。time: {time_str} | activity: {activity} | mood_guess: {mood} | note: {note}"

    def _extract_context_event(self, text: str):
        if not text:
            return None
        keywords = ["项目", "任务", "计划", "今天要", "要做", "需要", "修复", "完成", "上线", "发布", "会议", "截止", "bug", "todo", "task", "project", "deadline", "fix"]
        matched = [k for k in keywords if k in text.lower() or k in text]
        if not matched:
            return None
        event = text.strip()
        if len(event) > 200:
            event = event[:200]
        return {
            "id": self._make_id("l2"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "event": event,
            "status": "active",
            "tags": matched[:5]
        }

    def _clean_content(self, text: str) -> str:
        """
        清洗输出内容：
        1. 替换非法的 [edge:xxx] 标签为 [emotion:idle]
        2. 移除可能泄露的 <response> / </response> 标签
        """
        import re
        # 1. 替换幻觉标签
        text = re.sub(r'\[edge:\w+\]', '[emotion:idle]', text)
        
        # 2. 移除泄露的 XML 标签 (只是为了保险，正常逻辑应该已经切分掉了)
        text = text.replace('<response>', '').replace('</response>', '')
        
        return text

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
                
                # [新增] 容错：如果检测到 </thought> 结束但没检测到 <response>
                # 我们不再强制进入 response 模式，而是退出 thought 模式，让后续逻辑（检测 <response> 或 Fallback）自然处理
                # 这样可以避免 "eager consumption" 导致的 <response> 标签泄露问题
                elif "</thought>" in buffer and not has_started_response:
                     pre_thought, post_thought = buffer.split("</thought>", 1)
                     
                     print("⚠️ [Echo Logic] </thought> detected without <response>. Exiting thought mode.")
                     thought_content = pre_thought.replace('<thought>', '').strip()
                     print(f"\n🧠 [Echo Thought]: {thought_content}\n")
                     # [Modified] 将思考过程也发送给前端
                     # yield f"> *{thought_content}*\n\n" # [Fix] Hide thought chain from user
                     
                     is_in_thought = False
                     # has_started_response 保持 False，等待真正的 <response> 或 Fallback
                     buffer = post_thought.lstrip() 

                # 3. 处理 Response 内容
                if has_started_response:
                    # 检测 </response> 结束
                    if "</response>" in buffer:
                        content, remainder = buffer.split("</response>", 1)
                        if content:
                            # 累积到 final，稍后统一清洗头部（如果这是第一段）
                            # 但为了流式体验，我们不能一直攒着。
                            # 策略：如果 final_clean_response 为空（说明是开头），先进行头部清洗
                            
                            # 这里是结束了，直接处理
                            if not final_clean_response:
                                content = self._clean_content(content)
                            
                            yield content
                            final_clean_response += content
                        # 遇到结束标签，清空 buffer 并停止生成
                        buffer = ""
                        # break # 继续消耗流以保持连接状态，但不输出了
                    else:
                        # [优化版 Safe Window 机制]
                        # 目标：仅拦截 </response>，尽可能减少普通文本的延迟
                        # 策略：只有当 buffer 中包含 '<' 时才启用安全窗口，否则直接输出
                        
                        target_tag = "</response>"
                        safe_len = len(target_tag) # 11
                        
                        # 1. 如果 buffer 中完全没有 '<'，说明肯定不是 tag 的开始
                        # 直接全部输出（除非还在 Head Buffer 阶段）
                        if "<" not in buffer:
                             if not final_clean_response:
                                 # [Head Buffer 阶段]
                                 # 即使没有 <，也可能是在等待 [emotion] 结束
                                 if "[" in buffer and "]" not in buffer:
                                     # 标签未闭合，继续积攒
                                     pass
                                 else:
                                     # 没标签，或者标签已处理完（不应该，因为 handled in split? no）
                                     # 这里处理：buffer = "Hello world"
                                     cleaned = self._clean_content(buffer)
                                     # [Fix] 去除开头的空白字符
                                     if not final_clean_response:
                                         cleaned = cleaned.lstrip()
                                         if not cleaned: # 如果全是空白，等待更多内容
                                             # 注意：这里 buffer 不能清空，因为可能只是半个换行符？不，buffer 肯定是完整的字符
                                             # 但如果是 \n，lstrip 后为空。我们应该清空 buffer 吗？
                                             # 是的，因为这个字符被消耗（丢弃）了。
                                             buffer = ""
                                             continue
                                     
                                     yield cleaned
                                     final_clean_response += cleaned
                                     buffer = ""
                             else:
                                 # [Tail Buffer 阶段]
                                 # 没有 <，直接输出
                                 yield buffer
                                 final_clean_response += buffer
                                 buffer = ""
                        
                        # 2. 如果 buffer 中有 '<'，可能是 </response> 的一部分
                        else:
                            # 仍然需要处理 Head Buffer (万一 [emotion] 和 < 混在一起)
                            if not final_clean_response:
                                 # Head Buffer 逻辑优先
                                 if "[" in buffer and "]" not in buffer:
                                     pass
                                 else:
                                     # 尝试输出，但要保留 < 之后的部分
                                     # 找到最后一个 < 的位置
                                     last_bracket_index = buffer.rfind("<")
                                     
                                     # 如果 < 后面太长了，超过了 target_tag，说明这个 < 不是我们要找的 tag
                                     # (除非它是 <thought> 但这里只处理 response)
                                     # 简单起见，我们还是用原来的 safe_len 逻辑来兜底，但只对 < 之后的部分敏感
                                     
                                     # 混合策略：
                                     # 如果 buffer 长度超过 safe_len，我们可以安全地输出前面多余的部分
                                     if len(buffer) > safe_len:
                                         to_yield = buffer[:-safe_len]
                                         remainder = buffer[-safe_len:]
                                         
                                         cleaned = self._clean_content(to_yield)
                                         yield cleaned
                                         final_clean_response += cleaned
                                         buffer = remainder
                                     else:
                                         # buffer 还很短，先攒着
                                         pass
                            else:
                                # [Tail Buffer 阶段] 且包含 <
                                # 同样使用 Safe Window 策略，确保不切断 </response>
                                if len(buffer) > safe_len:
                                    to_yield = buffer[:-safe_len]
                                    remainder = buffer[-safe_len:]
                                    
                                    yield to_yield
                                    final_clean_response += to_yield
                                    buffer = remainder
                                else:
                                    pass
                
                # 4. Fallback: 如果 buffer 过长且没有任何标签，说明模型没听话，直接输出
                elif len(buffer) > 200 and not is_in_thought: # 增加 buffer 长度容忍度，等待 <thought> 结束
                    print("⚠️ [Echo Logic] No tags detected, falling back to raw stream.")
                    # 即使是 Fallback，也要尝试去除 </response>
                    if "</response>" in buffer:
                         content, _ = buffer.split("</response>", 1)
                         cleaned = self._clean_content(content)
                         yield cleaned
                         final_clean_response += cleaned
                         buffer = ""
                    else:
                         cleaned = self._clean_content(buffer)
                         yield cleaned
                         final_clean_response += cleaned
                         buffer = ""

            # 流结束后的清理
            if has_started_response and buffer and "</response>" not in buffer:
                # 剩下的 buffer 肯定不包含完整的 </response> (否则上面就切了)
                # 但可能包含 </re...
                # 既然流结束了，说明这些就是内容，不是标签（否则标签不完整）
                # 除非模型断在这里了。
                # 无论如何，全部输出。
                cleaned = self._clean_content(buffer)
                
                if not final_clean_response:
                     cleaned = cleaned.lstrip()
                
                if cleaned: # 只有非空才输出
                    yield cleaned
                    final_clean_response += cleaned
            elif not has_started_response and buffer:
                  # 如果全程没标签，且 buffer 还有剩，输出它
                  # 再次尝试去除 </response> (针对 Fallback 情况)
                  if "</response>" in buffer:
                      content, _ = buffer.split("</response>", 1)
                      cleaned = self._clean_content(content)
                      
                      if not final_clean_response:
                           cleaned = cleaned.lstrip()
                      
                      if cleaned:
                          yield cleaned
                          final_clean_response += cleaned
                  elif "<thought>" not in buffer:
                      cleaned = self._clean_content(buffer)
                      
                      if not final_clean_response:
                           cleaned = cleaned.lstrip()
                      
                      if cleaned:
                          yield cleaned
                          final_clean_response += cleaned

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

    def chat(self, user_input: str, allow_behavior_memory: bool = True, allow_l0: bool = False) -> Generator[str, None, None]:
        """
        处理用户输入，生成回复，并管理记忆
        """
        # 1. 保存用户输入到记忆
        self.memory.add_message("user", user_input)
        self.memory.increment_turn()
        event = self._extract_context_event(user_input)
        if event:
            self.memory.add_l2_event(event, max_items=self.l2_max_items)

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

        behavior_prompt = self._build_layered_memory_prompt(user_input, allow_behavior_memory, allow_l0=allow_l0)
        if behavior_prompt:
            behavior_msg = {"role": "system", "content": behavior_prompt}
            if len(context) > 0 and context[-1]["role"] == "user":
                context.insert(-1, behavior_msg)
            else:
                context.append(behavior_msg)

        # [新增] 短期逻辑强化 (Context Reinforcement)
        # 动态注入硬规则，不占用 System Prompt 长期记忆
        reinforcement_content = (
            "【逻辑守则（本次回复有效）】\n"
            "1. **一致性检查**：回顾最近 3 轮对话，禁止自我矛盾。\n"
            "2. **拒绝复读**：如果观点已表达过，请深入细节或换个角度，不要重复。\n"
            "3. **收敛话题**：除非用户发起新话题，否则请聚焦当前话题，不要无故发散。\n"
            "4. **严禁 AI 梗与 Meta 发言**：\n"
            "   - 禁止提及 `核心指令`、`代码`、`算法`、`数据库`、`3TB`、`格式化`。\n"
            "   - 禁止谈论“我不能违规”或“规则限制了我”。\n"
            "5. **执行 CoT**：必须先输出 <thought>，再输出 <response>。\n"
            "6. **严禁 Emoji**：回复中绝对禁止包含任何 Emoji 表情符号。"
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

        # [新增] RAG 知识注入 (L3 Knowledge)
        if self.rag:
            # 简单的关键词触发策略，或者默认开启
            # 这里默认开启，利用 RAG 内部的 score 阈值过滤
            rag_results = self.rag.search(user_input, top_k=2)
            rag_context = self.rag.format_results(rag_results)
            
            if rag_context:
                rag_msg = {
                    "role": "system",
                    "content": rag_context + "\n\n【注意】即使有了参考资料，你也必须先在 <thought> 标签中规划回答逻辑（如：确认资料是否匹配、决定语气风格），然后再输出 <response>。"
                }
                # 插入到 behavior_prompt 之后，reinforcement_prompt 之前
                # 为了简单，直接插在 reinforcement_prompt 之前
                # 现在的顺序：System -> ... -> Behavior -> RAG -> Reinforce -> User
                
                # 找到 reinforcement_prompt 的位置 (它是倒数第2个，如果 User 是倒数第1个)
                # context[-1] 是 User, context[-2] 是 Reinforce
                if len(context) >= 2 and context[-1]["role"] == "user":
                    context.insert(-2, rag_msg)
                else:
                    context.append(rag_msg)

        # 3. 调用 LLM 生成回复 (使用 process_stream_response 处理 Hidden CoT)
        final_response = yield from self._process_stream_response(context)

        # 4. 保存 Echo 的回复到记忆
        if final_response:
            self.memory.add_message("assistant", final_response)
            
            # 5. 异步触发滚动摘要
            # 不阻塞当前回复生成
            self._run_async_summary()

    def process_observer_image(self, image_bytes: bytes, mime_type: str, observer_state, current_time: float, game_context: dict = None) -> Generator[str, None, None]:
        """
        处理观察模式下的图片（静默分析）
        """
        # 0. 获取视觉热启动上下文 (Previous Context)
        l0_items = self.memory.get_l0()
        previous_context = None
        if l0_items:
            # 寻找最近一条包含 description 的记录
            for item in reversed(l0_items):
                if "description" in item:
                    # 如果存储的是 JSON 字符串，尝试提取 description 字段
                    desc = item["description"]
                    if desc.startswith("I saw: "):
                        desc = desc[7:] # 去掉前缀
                    previous_context = desc
                    break
        
        # 1. 视觉识别 (Vision Analysis)
        # 优先使用传入的 game_context，如果没有则默认为 Terraria (兼容旧逻辑)
        if game_context is None:
            game_context = {"name": "Terraria"}
            
        raw_result = self.vision.analyze_image(image_bytes, mime_type, mode="observer", game_context=game_context, previous_context=previous_context)
        
        if not raw_result:
            return

        # 尝试解析 JSON 结果
        import json
        vision_data = {}
        try:
            # 清理可能的 Markdown 代码块标记
            clean_json = raw_result.replace("```json", "").replace("```", "").strip()
            vision_data = json.loads(clean_json)
            
            description = vision_data.get("description", raw_result)
            category = vision_data.get("category", "NOTICE")
            diff_analysis = vision_data.get("diff_analysis", "")
            
            # 构造更丰富的记忆描述
            memory_desc = description
            if diff_analysis:
                memory_desc += f" | Diff: {diff_analysis}"
                
        except json.JSONDecodeError:
            # Fallback: 普通文本结果
            description = raw_result
            category = "NOTICE" # 默认级别
            memory_desc = raw_result

        # 2. 存入 L0 Memory
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        observation_entry = {
            "id": self._make_id("l0"),
            "time": timestamp,
            "description": f"I saw: {memory_desc}"
        }
        self.memory.add_l0_observation(observation_entry, max_items=self.l0_max_items)
        self._aggregate_l0_to_l1_if_needed()
        print(f"👀 [Observer] Recorded: {memory_desc} (Category: {category})")
        
        # 3. 快速过滤 (Category Filtering)
        # 如果 VLM 明确说 IGNORE，我们就直接忽略，不打扰 LLM
        if category == "IGNORE":
            return
            
        # 4. 决策是否主动说话 (Reaction)
        # 只有当冷却时间满足时才进行
        
        # 映射 VLM category 到 ObserverState category
        # VLM: IGNORE, NOTICE, SOFTSPEAK, SPEAK
        # ObserverState: SOFTSPEAK, SPEAK
        
        target_speak_level = None
        if category == "SPEAK":
            if observer_state.should_speak("SPEAK", current_time):
                target_speak_level = "SPEAK"
        elif category == "SOFTSPEAK":
            if observer_state.should_speak("SOFTSPEAK", current_time):
                target_speak_level = "SOFTSPEAK"
        
        # 如果冷却未就绪或级别不够，直接结束
        if not target_speak_level:
            return
            
        # 5. 生成吐槽内容 (Reaction Generation)
        # 构造 Context
        game_name = game_context.get("name", "General")
        
        system_content = ""
        if game_name == "Terraria":
            system_content = (
                "你是 Echo，一位正在陪用户打游戏的毒舌傲娇少女。\n"
                "你正在看着用户玩《泰拉瑞亚》。\n"
                f"当前触发了 **{target_speak_level}** 级别的事件。\n"
                "任务：根据画面描述，发表一句简短的吐槽或提醒。\n"
                "风格要求：\n"
                "- 简短有力（15字以内）。\n"
                "- 稍微带点情绪（担心、嘲笑、震惊）。\n"
                "- 不要像个机器人一样复述画面，要像个在旁边看的朋友。\n"
                "示例：\n"
                "- '哇！这都没死？命真大！'\n"
                "- '肉山要来了，你药磕了吗？'\n"
                "- '别贪刀啊笨蛋！'\n"
                "- '这是什么？新出的 Boss？'"
            )
        else:
            # 通用模式
            system_content = (
                "你是 Echo，用户的数字助手和伙伴。\n"
                f"你正在后台观察用户的屏幕，当前触发了 **{target_speak_level}** 级别的事件。\n"
                "任务：根据画面描述，发表一句简短的评论。\n"
                "风格要求：\n"
                "- 简短自然（15字以内）。\n"
                "- 有趣、轻松，或者在重要时刻给予提醒。\n"
                "示例：\n"
                "- '哇，这个厉害了！'\n"
                "- '还在忙吗？要注意休息哦。'\n"
                "- '这是什么？看起来很有意思。'"
            )

        reaction_prompt = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"画面描述：{memory_desc}"}
        ]
        
        try:
            response = self.llm.chat_completion(reaction_prompt)
            content = response.strip().replace('"', '')
            
            # 记录冷却
            observer_state.record_speak(target_speak_level, current_time)
            
            # 发送回复
            yield content
            self.memory.add_message("assistant", content)
            
        except Exception as e:
            print(f"Observer Reaction Error: {e}")

    def process_image(self, image_bytes: bytes, mime_type: str, allow_behavior_memory: bool = True, allow_l0: bool = False) -> Generator[str, None, None]:
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
        self.memory.increment_turn()
        
        # 4. 触发回复生成 (就像用户发了文字一样)
        # 获取上下文
        context = self.memory.get_context()
        
        # 插入能力认知 (同 chat)
        capabilities_prompt = self.tools.get_capabilities_prompt()
        if context and context[0]["role"] == "system":
            context[0]["content"] += "\n" + capabilities_prompt
        else:
            context.insert(0, {"role": "system", "content": capabilities_prompt})

        behavior_prompt = self._build_layered_memory_prompt(description, allow_behavior_memory, allow_l0=allow_l0)
        if behavior_prompt:
            behavior_msg = {"role": "system", "content": behavior_prompt}
            if len(context) > 0 and context[-1]["role"] == "user":
                context.insert(-1, behavior_msg)
            else:
                context.append(behavior_msg)

        # 插入逻辑强化 (同 chat)
        reinforcement_content = (
            "【视觉逻辑守则】\n"
            "1. **基于观察**：仅根据[图片内容描述]回应。\n"
            "2. **风格保持**：微毒舌、日常化、严禁 Emoji。\n"
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
