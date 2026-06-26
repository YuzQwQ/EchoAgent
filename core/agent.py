from typing import Generator, Optional, Dict, Any
from datetime import datetime, timezone
from core.llm_service import LLMService
from core.vision_service import VisionService
from core.memory import MemoryManager
from core.rag_service import RAGService
from core.tools.base import ToolRegistry
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
        from core.tools.system_tools import (
            VisionCapabilityTool, 
            TTSCapabilityTool, 
            MemoryCapabilityTool, 
            SystemSelfAwarenessTool,
            ProjectHistoryTool,
            GetCurrentTimeTool,
            CreateTextFileTool,
            WriteTextFileTool,
            AppendTextFileTool,
            ReadTextFileTool,
            CopyToClipboardTool,
            ReadClipboardTool,
            ListWindowsTool,
            ScreenshotWindowTool,
            ObserveWindowTool
        )
        self.tools.register(VisionCapabilityTool())
        self.tools.register(TTSCapabilityTool())
        self.tools.register(MemoryCapabilityTool())
        self.tools.register(SystemSelfAwarenessTool())
        self.tools.register(ProjectHistoryTool())
        self.tools.register(GetCurrentTimeTool())
        self.tools.register(CreateTextFileTool())
        self.tools.register(WriteTextFileTool())
        self.tools.register(AppendTextFileTool())
        self.tools.register(ReadTextFileTool())
        self.tools.register(CopyToClipboardTool())
        self.tools.register(ReadClipboardTool())
        self.tools.register(ListWindowsTool())
        self.tools.register(ScreenshotWindowTool())
        self.tools.register(ObserveWindowTool())

    def refresh_runtime_resources(self):
        """Rebuild workspace-bound resources after runtime config changes."""
        try:
            self.memory.flush()
        except Exception:
            pass
        self.memory = MemoryManager()
        self.tools = ToolRegistry()
        self._register_core_tools()

    def add_observation_to_context(self, observation: str):
        """
        将观察到的事件添加到短期记忆 (Context) 中，但不触发回复。
        这让 Echo 拥有“上帝视角”，知道用户刚才干了什么。
        """
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
        
        perceptual_context = ""
        l0_items = self.memory.get_l0()
        if l0_items and allow_l0:
            latest_obs = l0_items[-1] # 取最新一条
            obs_time_str = latest_obs.get("time", "")
            # 检查时效性 (假设 time 格式为 "%Y-%m-%d %H:%M:%S" 或 "%Y-%m-%d %H:%M")
            # 这里简单起见，只要是最新一条且非空，就认为是有效的 Perceptual Context
            desc = latest_obs.get("description", "")
            if desc and "IGNORE" not in desc: # 排除被标记为忽略的
                perceptual_context = f"【系统实时感知 (Perceptual Context)】\nEcho 刚刚观察到的现实世界状态（具有最高事实优先级）：\n- 时间: {obs_time_str}\n- 画面内容: {desc}\n"

        # 2. 常规记忆检索 (L1/L2)
        current_turn = self.memory.get_turn()
        l1_items = self.memory.get_l1()
        l2_items = self.memory.get_l2()
        
        selected = self._select_relevant_from_layer(l1_items, query, current_turn)
        if not selected:
            selected = self._select_relevant_from_layer(l2_items, query, current_turn)
            
        # 3. L0 检索 (作为 Perceptual Context 的补充，或用于查找更早的细节)
        # 如果已经有了 Perceptual Context，这里的检索可能就不那么重要了，但还是保留以防万一
        if not selected and allow_l0:
            selected = self._select_relevant_from_l0(query, current_turn)

        memory_prompt = ""
        if selected:
            selected_id = selected.get("id", "")
            if selected_id:
                self.memory.update_cooldown(selected_id, current_turn)
            
            if "event" in selected:
                time_str = selected.get("time", "")
                event = selected.get("event", "")
                status = selected.get("status", "")
                memory_prompt = f"【历史记忆检索】time: {time_str} | event: {event} | status: {status}"
            elif "description" in selected:
                # 如果检索到的就是最新那条，为了避免重复，可以跳过（或者 Perceptual Context 已经覆盖了）
                # 但简单起见，重复也无妨，强化印象
                time_str = selected.get("time", "")
                desc = selected.get("description", "")
                memory_prompt = f"【历史观察回溯】time: {time_str} | description: {desc}"
            else:
                time_str = selected.get("time", "")
                activity = selected.get("activity", "")
                mood = selected.get("mood_guess", "")
                note = selected.get("note", "")
                memory_prompt = f"【历史行为片段】time: {time_str} | activity: {activity} | mood_guess: {mood} | note: {note}"

        # 4. 组合最终 Prompt
        # Perceptual Context 必须放在最前面，且明确标识
        final_prompt = ""
        if perceptual_context:
            final_prompt += perceptual_context + "\n"
        
        if memory_prompt:
            final_prompt += memory_prompt
            
        return final_prompt if final_prompt else None

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
        
        text = text.replace('<response>', '').replace('</response>', '')
        
        return text

    def _process_stream_response(self, context, trace_id: Optional[str] = None) -> Generator[str, None, str]:
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
            for chunk in self.llm.chat_stream(context, trace_id=trace_id):
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
                
                elif "</thought>" in buffer and not has_started_response:
                     pre_thought, post_thought = buffer.split("</thought>", 1)
                     
                     print("⚠️ [Echo Logic] </thought> detected without <response>. Exiting thought mode.")
                     thought_content = pre_thought.replace('<thought>', '').strip()
                     print(f"\n🧠 [Echo Thought]: {thought_content}\n")
                     
                     is_in_thought = False
                     has_started_response = True
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
                                     # 这里处理：buffer = "Hello world"
                                     cleaned = self._clean_content(buffer)
                                     # [Fix] 去除开头的空白字符
                                     if not final_clean_response:
                                         cleaned = cleaned.lstrip()
                                         if not cleaned: # 如果全是空白，等待更多内容
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
                elif len(buffer) > 80 and not is_in_thought:
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

    def _build_tool_selection_prompt(self) -> str:
        return (
            "【工具选择规则】\n"
            "只使用已注册工具的 canonical name，不要创造工具名或使用别名。\n"
            "create_text_file：只用于创建新的空 .txt 文件。\n"
            "write_text_file：用于覆盖写入 .txt 文件，会替换原有内容。\n"
            "append_text_file：用于把新内容追加到 .txt 文件末尾；文件不存在时也可以创建。\n"
            "read_text_file：只用于读取或查看文件内容。\n"
            "不要用 read_text_file 代替 write_text_file 或 append_text_file；用户要求新增、加入、补充、追加内容时，应选择 append_text_file。\n"
            "如果缺少工具必需参数，返回普通文本询问用户，不要调用参数不完整的工具。"
        )

    def _build_post_tool_response_prompt(self) -> str:
        return (
            "【工具结果回复规则】\n"
            "工具已经执行完毕。接下来请基于工具返回的真实结果，用 Echo 的正常聊天语气回复用户。\n"
            "不要逐字照搬工具返回的方括号状态标签，也不要像系统日志广播。"
            "成功时简短确认做了什么，必要时自然带上路径、文件名或读取到的内容；"
            "失败时说明失败原因或缺少什么参数。"
            "严禁声称工具结果之外的事情已经发生。"
        )

    def chat(self, user_input: str, allow_behavior_memory: bool = True, allow_l0: bool = False, event_sink=None) -> Generator[str, None, None]:
        """
        处理用户输入，生成回复，并管理记忆
        包含：RAG、Context构建、Tool Call、流式生成
        """
        import uuid
        import time
        trace_id = uuid.uuid4().hex[:8]
        start_time = time.monotonic()
        print(f"[trace:{trace_id}] chat_start")
        self._emit_trace(
            event_sink,
            trace_id,
            "chat_start",
            message="Chat request started",
            input_preview=user_input,
        )

        self.memory.add_message("user", user_input)
        self.memory.increment_turn()
        event = self._extract_context_event(user_input)
        if event:
            self.memory.add_l2_event(event, max_items=self.l2_max_items)

        context = self.memory.get_context()

        behavior_prompt = self._build_layered_memory_prompt(user_input, allow_behavior_memory, allow_l0=allow_l0)
        if behavior_prompt:
            behavior_msg = {"role": "system", "content": behavior_prompt}
            if len(context) > 0 and context[-1]["role"] == "user":
                context.insert(-1, behavior_msg)
            else:
                context.append(behavior_msg)

        reinforcement_content = (
            "【守则】\n"
            "1. **一致性**：不自相矛盾，不复读。\n"
            "2. **聚焦**：除非用户转话题，否则聚焦当前。\n"
            "3. **禁忌**：禁 AI 梗、Emoji、Meta 发言。\n"
            "4. **格式**：先 <thought> 后 <response>。\n"
            "5. **事实**：客观事实（时间/剪贴板/文件）必须用工具，严禁编造操作结果。"
        )
        reinforcement_prompt = {
            "role": "system",
            "content": reinforcement_content
        }
        if len(context) > 0 and context[-1]["role"] == "user":
            context.insert(-1, reinforcement_prompt)
        else:
            context.append(reinforcement_prompt)

        should_use_rag = False
        if self.rag:
            rag_keywords = [
                "泰拉瑞亚", "terraria", "boss", "npc", "武器", "配饰", "药水",
                "事件", "生物群落", "攻略", "流程", "指南"
            ]
            lower_input = user_input.lower()
            should_use_rag = any(k in user_input for k in rag_keywords) or any(k in lower_input for k in rag_keywords)

        if self.rag and should_use_rag:
            rag_results = self.rag.search(user_input, top_k=1)
            rag_context = self.rag.format_results(rag_results)
            
            if rag_context:
                rag_msg = {
                    "role": "system",
                    "content": rag_context + "\n\n【注意】即使有了参考资料，你也必须先在 <thought> 标签中规划回答逻辑（如：确认资料是否匹配、决定语气风格），然后再输出 <response>。"
                }
                if len(context) >= 2 and context[-1]["role"] == "user":
                    context.insert(-2, rag_msg)
                else:
                    context.append(rag_msg)

        tool_info = self._run_tool_loop(context, event_sink=event_sink, trace_id=trace_id)
        if tool_info:
            print(f"[trace:{trace_id}] tool_check tool_calls={tool_info.get('tool_calls')}")
            text_response = tool_info.get("text_response")
            if text_response is not None:
                text_response = self._clean_non_stream_response(str(text_response))
                self.memory.add_message("assistant", text_response)
                self._run_async_summary()
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                print(f"[trace:{trace_id}] chat_end elapsed_ms={elapsed_ms} response_chars={len(text_response)}")
                self._emit_trace(
                    event_sink,
                    trace_id,
                    "chat_end",
                    message="Chat request finished",
                    elapsed_ms=elapsed_ms,
                    response_chars=len(text_response),
                    tool_calls=tool_info.get("tool_calls", 0),
                )
                yield text_response
                return

        self._emit_trace(
            event_sink,
            trace_id,
            "llm_request",
            message="Requesting streaming assistant response",
            model=getattr(config, "PRIMARY_MODEL_NAME", ""),
            mode="stream",
            round=0,
        )
        final_response = yield from self._process_stream_response(context, trace_id=trace_id)

        if final_response:
            self.memory.add_message("assistant", final_response)
            self._run_async_summary()

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        print(f"[trace:{trace_id}] chat_end elapsed_ms={elapsed_ms} response_chars={len(final_response or '')}")
        self._emit_trace(
            event_sink,
            trace_id,
            "chat_end",
            message="Chat request finished",
            elapsed_ms=elapsed_ms,
            response_chars=len(final_response or ""),
            tool_calls=0,
        )

    def process_observer_image(self, image_bytes: bytes, mime_type: str, observer_state, current_time: float, game_context: Optional[Dict[str, Any]] = None) -> Generator[str, None, None]:
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
        description = self.vision.analyze_image(image_bytes, mime_type)
        
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
        max_msgs = config.MAX_HISTORY_ROUNDS * 2
        
        if len(history) > max_msgs:
            old_messages = self.memory.pop_oldest_messages(2)
            if not old_messages:
                return

            current_summary = self.memory.get_summary()
            
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
            import uuid
            trace_id = uuid.uuid4().hex[:8]
            for chunk in self._process_stream_response(context, trace_id=trace_id):
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

    def _parse_tool_arguments(self, raw_arguments: str):
        if raw_arguments is None:
            return None, "Tool arguments missing"
        if isinstance(raw_arguments, dict):
            return raw_arguments, None
        try:
            import json
            return json.loads(raw_arguments), None
        except Exception:
            pass
        cleaned = raw_arguments.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            import json
            return json.loads(cleaned), None
        except Exception as e:
            return None, f"Invalid tool arguments: {str(e)}"

    def _clean_non_stream_response(self, text: str) -> str:
        import re
        if not text:
            return ""
        if "<response>" in text:
            text = text.split("<response>", 1)[1]
            if "</response>" in text:
                text = text.split("</response>", 1)[0]
        text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
        return self._clean_content(text).strip()

    def _tool_call_to_dict(self, tool_call) -> Dict[str, Any]:
        function = getattr(tool_call, "function", None)
        return {
            "id": getattr(tool_call, "id", ""),
            "type": getattr(tool_call, "type", "function"),
            "function": {
                "name": getattr(function, "name", "") if function is not None else "",
                "arguments": getattr(function, "arguments", "") if function is not None else "",
            }
        }

    def _assistant_tool_call_message(self, tool_call_result, tool_calls: list) -> Dict[str, Any]:
        content = getattr(tool_call_result, "content", None)
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [self._tool_call_to_dict(tool_call) for tool_call in tool_calls],
        }

    def _tool_action(self, tool_name: str) -> str:
        actions = {
            "create_text_file": "create",
            "write_text_file": "write",
            "append_text_file": "append",
            "read_text_file": "read",
            "copy_to_clipboard": "copy",
            "read_clipboard": "read",
            "list_windows": "list",
            "screenshot_window": "screenshot",
            "observe_window": "observe",
            "GetCurrentTime": "read",
            "ProjectHistory": "read",
        }
        return actions.get(tool_name, "execute")

    def _classify_tool_error(self, message: str) -> str:
        if "缺少" in message:
            return "missing_argument"
        if "不存在" in message:
            return "not_found"
        if "路径" in message or ".txt" in message or "相对" in message or "逃逸" in message:
            return "invalid_path"
        if "Invalid tool arguments" in message or "arguments" in message:
            return "invalid_arguments"
        return "tool_failure"

    def _extract_tool_path(self, result: str, kwargs: Optional[Dict[str, Any]]) -> Optional[str]:
        if isinstance(result, str) and "】" in result:
            remainder = result.split("】", 1)[1].strip()
            first_line = remainder.splitlines()[0].strip() if remainder else ""
            if first_line and not first_line.startswith("【") and (":\\" in first_line or first_line.endswith(".txt") or first_line.endswith(".png")):
                return first_line
        if kwargs:
            path = kwargs.get("path") or kwargs.get("window_title")
            if path:
                return str(path)
        return None

    def _content_preview(self, tool_name: str, result: str, kwargs: Optional[Dict[str, Any]]) -> Optional[str]:
        preview = None
        if tool_name == "read_text_file" and isinstance(result, str) and "\n" in result:
            preview = result.split("\n", 1)[1].strip()
            if preview.startswith("【内容为空】"):
                preview = ""
        elif kwargs and "content" in kwargs:
            preview = str(kwargs.get("content") or "")
        if preview is None:
            return None
        if len(preview) > 500:
            return preview[:500] + "..."
        return preview

    def _build_tool_payload(
        self,
        tool_name: str,
        kwargs: Optional[Dict[str, Any]],
        result,
        ok: bool,
        error_type: Optional[str] = None
    ) -> Dict[str, Any]:
        message = str(result)
        payload = {
            "ok": ok,
            "tool": tool_name,
            "action": self._tool_action(tool_name),
            "message": message,
        }
        path = self._extract_tool_path(message, kwargs)
        if path:
            payload["path"] = path
        preview = self._content_preview(tool_name, message, kwargs)
        if preview is not None:
            payload["content_preview"] = preview
        if not ok:
            payload["error_type"] = error_type or self._classify_tool_error(message)
        return payload

    def _trace_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sanitize_trace_value(self, value, key: Optional[str] = None, limit: int = 500, depth: int = 0):
        secret_keys = ("api_key", "token", "authorization", "password", "secret", "access_token", "admin_token")
        key_name = (key or "").lower()
        if any(secret in key_name for secret in secret_keys):
            return "[redacted]"
        if depth > 4:
            return "[max_depth]"
        if isinstance(value, dict):
            return {
                str(k): self._sanitize_trace_value(v, key=str(k), limit=limit, depth=depth + 1)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._sanitize_trace_value(item, limit=limit, depth=depth + 1) for item in value[:20]]
        if isinstance(value, bytes):
            return f"[bytes omitted length={len(value)}]"
        if isinstance(value, str):
            import re
            compact = value.strip()
            if compact.startswith("data:") and "base64," in compact:
                return f"[data-url omitted length={len(value)}]"
            looks_base64 = len(compact) > 120 and re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", compact)
            base64_field = "base64" in key_name or key_name in {"image", "audio", "image_data", "audio_data"}
            if looks_base64 and (base64_field or any(char in compact for char in "+/=")):
                return f"[base64 omitted length={len(value)}]"
            if len(value) > limit:
                return value[:limit] + "...[truncated]"
            return value
        return value

    def _emit_trace(self, event_sink, trace_id: str, event: str, level: str = "info", message: str = "", **fields):
        if event_sink is None:
            return
        payload = {
            "type": "trace_event",
            "trace_id": trace_id,
            "event": event,
            "level": level,
            "timestamp": self._trace_timestamp(),
            "message": message,
        }
        for key, value in fields.items():
            payload[key] = self._sanitize_trace_value(value, key=key)
        try:
            event_sink(payload)
        except Exception as e:
            print(f"[trace:{trace_id}] trace_sink_error {e}")

    def _run_tool_calls(self, context, user_input: str = ""):
        return self._run_tool_loop(context)

    def _run_tool_loop(self, context, max_tool_rounds: int = 5, event_sink=None, trace_id: Optional[str] = None):
        tools_schema = [t.to_dict() for t in self.tools.get_all_tools()]
        if not tools_schema:
            return None

        tool_context = context
        tool_selection_prompt = {"role": "system", "content": self._build_tool_selection_prompt()}
        if tool_context and tool_context[-1].get("role") == "user":
            tool_context.insert(-1, tool_selection_prompt)
        else:
            tool_context.append(tool_selection_prompt)
        post_tool_prompt_added = False
        total_tool_calls = 0
        executed_tools = []

        try:
            import json
            import time
            available_tools = ", ".join(tool.name for tool in self.tools.get_all_tools())
            for round_index in range(max_tool_rounds):
                llm_start = time.monotonic()
                self._emit_trace(
                    event_sink,
                    trace_id or "",
                    "llm_request",
                    message="Requesting model tool decision",
                    model=getattr(config, "PRIMARY_MODEL_NAME", ""),
                    round=round_index + 1,
                    mode="tools",
                )
                tool_call_result = self.llm.chat_completion_with_tools(
                    tool_context,
                    tools=tools_schema,
                    tool_choice=None,
                )
                if tool_call_result is None:
                    return None

                tool_calls = list(getattr(tool_call_result, 'tool_calls', None) or [])
                self._emit_trace(
                    event_sink,
                    trace_id or "",
                    "llm_response",
                    message="Model tool decision received",
                    model=getattr(config, "PRIMARY_MODEL_NAME", ""),
                    round=round_index + 1,
                    tool_calls_count=len(tool_calls),
                    elapsed_ms=int((time.monotonic() - llm_start) * 1000),
                )
                if not tool_calls:
                    return {
                        "tool_calls": total_tool_calls,
                        "executed_tools": executed_tools,
                        "text_response": getattr(tool_call_result, "content", "") or "",
                    }

                total_tool_calls += len(tool_calls)
                tool_context.append(self._assistant_tool_call_message(tool_call_result, tool_calls))

                for call_index, tool_call in enumerate(tool_calls):
                    function = getattr(tool_call, "function", None)
                    function_name = getattr(function, "name", "")
                    raw_arguments = getattr(function, "arguments", None)
                    kwargs, arg_error = self._parse_tool_arguments(raw_arguments)
                    call_id = getattr(tool_call, "id", "") or f"call_{round_index}_{call_index}"
                    tool_instance = self.tools.get_tool(function_name)
                    self._emit_trace(
                        event_sink,
                        trace_id or "",
                        "tool_call",
                        message=f"{function_name} call requested",
                        tool=function_name,
                        action=self._tool_action(function_name),
                        round=round_index + 1,
                        tool_call_id=call_id,
                        arguments=kwargs if kwargs is not None else raw_arguments,
                    )

                    if tool_instance is None:
                        result = f"工具 {function_name} 不存在。可用工具：{available_tools}"
                        ok = False
                        error_type = "unknown_tool"
                    elif kwargs is None:
                        result = arg_error or "Invalid tool arguments"
                        ok = False
                        error_type = "invalid_arguments"
                    else:
                        try:
                            result = tool_instance.execute(**kwargs)
                            ok = not (isinstance(result, str) and ("失败" in result or result.startswith("Error")))
                            error_type = None if ok else self._classify_tool_error(str(result))
                        except Exception as e:
                            result = f"执行 {function_name} 时出错：{str(e)}"
                            ok = False
                            error_type = "execution_exception"

                    tool_payload = self._build_tool_payload(function_name, kwargs, result, ok, error_type)
                    trace_tool_payload = {key: value for key, value in tool_payload.items() if key != "message"}
                    self._emit_trace(
                        event_sink,
                        trace_id or "",
                        "tool_result",
                        level="info" if ok else "error",
                        message=tool_payload.get("message", ""),
                        **trace_tool_payload,
                    )
                    tool_context.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(tool_payload, ensure_ascii=False)
                    })
                    executed_tools.append({
                        "tool": function_name,
                        "kwargs": kwargs,
                        "result": result,
                        "payload": tool_payload,
                    })

                if not post_tool_prompt_added:
                    tool_context.append({"role": "system", "content": self._build_post_tool_response_prompt()})
                    post_tool_prompt_added = True

            tool_context.append({
                "role": "system",
                "content": "工具调用轮次已达到上限。请停止调用工具，基于已有工具结果用自然语言向用户说明当前状态和下一步建议。"
            })

            self._emit_trace(
                event_sink,
                trace_id or "",
                "tool_loop_limit",
                level="error",
                message="Tool loop reached max rounds",
                max_tool_rounds=max_tool_rounds,
                tool_calls=total_tool_calls,
            )

            return {
                "tool_calls": total_tool_calls,
                "executed_tools": executed_tools,
                "text_response": "工具调用次数过多，已停止继续执行。请确认要继续做什么。",
            }
        except Exception as e:
            print(f"Tool loop failed: {e}")
            self._emit_trace(
                event_sink,
                trace_id or "",
                "error",
                level="error",
                message=f"Tool loop failed: {str(e)}",
                error_type="tool_loop_exception",
            )
            return {
                "tool_calls": 0,
                "executed_tools": [],
                "text_response": None,
            }
    
    def get_history(self):
        return self.memory.load_history()

    def clear_memory(self):
        self.memory.clear_history()
