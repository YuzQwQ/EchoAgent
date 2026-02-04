from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from core.agent import EchoAgent
from core.tts_service import TTSService
from config import config
import uvicorn
import asyncio
import json
import base64
import re
import speech_recognition as sr
import io

app = FastAPI(title="Echo API Service")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载前端静态文件 (实现 HTTP 托管)
# 注意：必须先定义具体的 API 路由，最后再挂载 "/"，否则静态文件路由会拦截所有请求
# 为了避免 WebSocket 被拦截，我们把静态文件挂载到 "/ui" 或者确保它不覆盖 WebSocket 路由
# FastAPI 的 mount 顺序很重要。

# 方案：将静态文件挂载调整到文件末尾，或者使用具体路径
# 由于我们需要访问根路径 "/"，所以必须小心。
# WebSocket 路由 "/ws/chat" 应该在 mount "/" 之前定义吗？
# 不，FastAPI 的路由匹配是按顺序的，但 mount "/" 作为一个 catch-all 可能会有问题。

# 修正：将 mount 移动到文件最底部，或者确保 WebSocket 路由先被注册。
# 但在这里，WebSocket 路由是在 @app.websocket 装饰器中定义的，通常会在启动时注册。
# 关键问题是：StaticFiles 中间件可能会拦截 WebSocket 握手请求 (因为它只处理 http scope)。

# 解决方法：不要挂载到根路径 "/"，或者自定义 StaticFiles 来忽略 WebSocket。
# 或者，最简单的：把 WebSocket 路由定义移到 mount 之前？(Python 代码执行顺序)
# 实际上 @app.websocket 只是注册路由，真正的请求处理顺序取决于 Starlette 的路由表顺序。
# 显式挂载 "/" 会匹配所有路径。

# 最佳实践：
# 1. 先定义 API 和 WebSocket 路由。
# 2. 最后挂载静态文件到 "/"。

# 我们先把这里的 mount 代码删掉，移动到文件末尾。
pass

# 初始化 Agent 和 TTS
agent = EchoAgent()
tts_service = TTSService()

class ObserverState:
    """观察模式全局状态管理"""
    def __init__(self):
        self.last_speak_time = 0
        self.last_soft_speak_time = 0
        
        # [Speech Budget] 说话预算池
        # 允许短时间内 burst 输出，但长期受限
        # 简化版：滑动窗口计数器
        self.speak_history = [] # 记录过去 N 分钟的说话时间戳
        self.BUDGET_WINDOW = 300 # 5分钟窗口
        self.MAX_SPEAK_IN_WINDOW = 2 # 5分钟内最多主动说话 2 次
        
        # [Soft Context] 内部积累状态
        self.soft_context = {
            "current_activity": "",
            "since": 0,
            "last_update": 0,
            "observation_count": 0
        }
        
    def update_soft_context(self, description: str, current_time: float):
        """
        更新 Soft Context，积累观察状态
        这里简单实现：更新时间戳和计数
        未来可以做更复杂的语义聚合（判断是否还在做同一件事）
        """
        # 简单的活性衰减检查
        if current_time - self.soft_context["last_update"] > 600: # 10分钟无更新，重置
            self.soft_context["current_activity"] = ""
            self.soft_context["since"] = current_time
            self.soft_context["observation_count"] = 0
            
        self.soft_context["last_update"] = current_time
        self.soft_context["observation_count"] += 1
        
        # 简单覆盖 Activity (未来可以用 LLM 总结)
        if not self.soft_context["current_activity"]:
            self.soft_context["current_activity"] = description
            self.soft_context["since"] = current_time
            
    def check_speech_budget(self, current_time: float) -> bool:
        """检查是否有说话余额"""
        # 1. 清理过期记录
        self.speak_history = [t for t in self.speak_history if current_time - t < self.BUDGET_WINDOW]
        
        # 2. 检查余额
        if len(self.speak_history) >= self.MAX_SPEAK_IN_WINDOW:
            print(f"[Observer] Budget exhausted: {len(self.speak_history)}/{self.MAX_SPEAK_IN_WINDOW} in {self.BUDGET_WINDOW}s")
            return False
        return True

    def should_speak(self, category: str, current_time: float) -> bool:
        # 1. 更新 Soft Context (无论是否说话)
        # 注意：这里假设外部调用 update_soft_context，或者在这里调用？
        # 为了解耦，should_speak 只做决策
        
        # [重构] 重新定义等级职责
        # IGNORE: 啥也不干
        # NOTICE / SOFTSPEAK: 积累 Context，默认不说话，除非 Budget 溢出或者有特殊触发
        # SPEAK: 消耗 Budget，尝试说话
        
        if category == "IGNORE":
            return False
            
        if category == "NOTICE" or category == "SOFTSPEAK":
            # 默认闭嘴，只积累
            # 除非：用户长时间没互动了，且 Budget 充足，偶尔冒泡 (低概率)
            
            # 检查 Budget
            if not self.check_speech_budget(current_time):
                return False
                
            # 只有 SOFTSPEAK 有机会低概率冒泡
            if category == "SOFTSPEAK":
                 # 极低概率主动搭话 (例如 5% -> 10% 稍微调高一点，增加点存在感)
                 import random
                 if random.random() < 0.10:
                     return True
            return False

        if category == "SPEAK":
            # 强打断事件
            # 检查 Budget
            if not self.check_speech_budget(current_time):
                # 即使是 SPEAK，如果 Budget 没了也得闭嘴 (或者可以设计 Emergency Override)
                return False
            
            # 必须说话
            return True
            
        return False

    def record_speak(self, category: str, current_time: float):
        # 消耗 Budget
        self.speak_history.append(current_time)
        
        if category == "SPEAK":
            self.last_speak_time = current_time
        elif category == "SOFTSPEAK":
            self.last_soft_speak_time = current_time

    def reset_cooldown(self):
        """用户主动交互时重置冷却和 Budget"""
        self.last_speak_time = 0
        self.last_soft_speak_time = 0
        # 用户主动说话了，说明愿意聊，清空 Budget 计数，允许 Echo 继续跟进
        self.speak_history = []

observer_state = ObserverState()

def sanitize_text_for_tts(text: str) -> str:
    """
    清洗文本，去除不适合 TTS 朗读的符号（如 Emoji、Markdown、动作描写、情感标签）
    """
    # 0. [新增] 去除情感标签 [emotion:xxx] 和其他可能的标签
    # 匹配 [key:value] 格式，更宽泛地匹配 value 部分，防止特殊字符漏网
    text = re.sub(r'\[\w+:[^\]]+\]', '', text)
    
    # 1. 去除 Emoji (简单范围匹配)
    # 这是一个比较宽泛的 regex，匹配常见 emoji 和图形符号
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # 2. 去除 Markdown 粗体/斜体符号 (*, **)
    text = text.replace("**", "").replace("*", "")
    
    # 3. 去除括号内的动作描写 (e.g., （笑）, (叹气))
    # 匹配中文全角括号和英文半角括号
    text = re.sub(r'（.*?）', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    
    # 4. 替换换行符为逗号或句号，增加自然停顿
    text = text.replace("\n", "，")
    
    # 5. 去除多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

from core.vision_service import VisionService
import time

vision_service = VisionService()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_input = message_data.get("content", "")
            msg_type = message_data.get("type", "text") # text, image, audio, auto_observe
            enable_tts = message_data.get("enable_tts", False) # 接收前端开关状态
            allow_behavior_memory = True
            allow_l0 = False

            # 用户主动交互，重置冷却时间
            if msg_type in ["text", "audio", "image"]:
                observer_state.reset_cooldown()

            # 处理自动观察 (Auto Observe)
            if msg_type == "auto_observe":
                try:
                    image_data_str = message_data.get("content", "")
                    if "base64," in image_data_str:
                         _, encoded = image_data_str.split("base64,", 1)
                         image_bytes = base64.b64decode(encoded)
                    else:
                         image_bytes = base64.b64decode(image_data_str)
                    
                    # 1. 调用 Vision Service 分析 (Mode=observer)
                    # 这里的 analyze_image 现在返回 JSON 字符串
                    analysis_result_json = vision_service.analyze_image(image_bytes, mode="observer")
                    
                    try:
                        # 尝试解析 JSON
                        # 有时候 LLM 即使被要求返回 JSON，也可能带 Markdown 代码块，需清洗
                        clean_json = analysis_result_json.replace("```json", "").replace("```", "").strip()
                        analysis_data = json.loads(clean_json)
                        
                        description = analysis_data.get("description", "")
                        category = analysis_data.get("category", "IGNORE")
                        
                        print(f"[Observer] Category: {category}, Desc: {description}")
                        
                        # 2. 决策逻辑
                        current_ts = time.time()
                        
                        # [Refactor] 更新 Soft Context (始终执行)
                        observer_state.update_soft_context(description, current_ts)
                        
                        should_speak = observer_state.should_speak(category, current_ts)
                        
                        if should_speak:
                            # 触发主动回复
                            print(f"[Observer] Triggering Echo response ({category})...")
                            observer_state.record_speak(category, current_ts)
                            
                            # 构造观察模式的输入
                            interaction_hint = ""
                            if category == "SOFTSPEAK":
                                # Level 1.5: 轻度共鸣 (提示 Agent 简短一点)
                                # [优化] 增加随机指令，避免每次都说类似的话
                                import random
                                hints = [
                                    "（请进行极简短的互动，表示你在陪着我，不要长篇大论）",
                                    "（请用好奇的语气问我在做什么，只说一句话）",
                                    "（请用慵懒的语气评价一下当前的画面，简短点）",
                                    "（如果不感兴趣，就简单哼一声或者发个语气词）"
                                ]
                                interaction_hint = random.choice(hints)
                            else:
                                # Level 2: 重点吐槽 (SPEAK)
                                interaction_hint = "（请根据画面内容进行吐槽或情绪共鸣，语气自然一点）"
                            
                            # 将观察结果封装为特殊的文本输入
                            observe_input = f"【系统视觉观察】用户屏幕当前显示：{description}。{interaction_hint}"
                            
                            # 借用 text 类型的处理流程
                            user_input = observe_input
                            msg_type = "text" # 转入通用回复流程
                            
                            # 开启记忆关联，确保“逻辑”一致性
                            allow_behavior_memory = True 
                            allow_l0 = True # 允许访问短期观察记录
                            
                        else:
                            # 即使不说话，如果不是 IGNORE，也应该把这个信息存入 Agent 的短期记忆（Context）
                            # 这样用户下次说话时，Echo 知道刚才发生了什么
                            if category != "IGNORE":
                                # 存入 L0，作为 Perceptual Context 的来源
                                agent.add_observation_to_context(description)
                                print(f"[Observer] Silent observation recorded (Category: {category})")
                            
                            continue # 不触发回复

                    except json.JSONDecodeError:
                        print(f"[Observer] JSON Parse Error: {analysis_result_json}")
                        continue

                except Exception as e:
                    print(f"[Observer] Error: {str(e)}")
                    continue

            # 处理语音消息 (STT)
            if msg_type == "audio":
                try:
                    # 1. 解码 Base64
                    audio_data_str = user_input
                    if "base64," in audio_data_str:
                        _, encoded = audio_data_str.split("base64,", 1)
                        audio_bytes = base64.b64decode(encoded)
                    else:
                        audio_bytes = base64.b64decode(audio_data_str)
                    
                    # 2. 使用 SpeechRecognition 处理
                    r = sr.Recognizer()
                    # 这里的 BytesIO 必须包含完整的 WAV 文件数据（含头信息）
                    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                        audio = r.record(source)
                    
                    # 3. 调用 Google STT (需联网)
                    print("Recognizing speech...")
                    # show_all=False 返回最佳结果字符串
                    # 使用 run_in_executor 避免阻塞事件循环
                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(None, lambda: r.recognize_google(audio, language="zh-CN"))
                    print(f"Recognized text: {text}")
                    
                    if text:
                        user_input = text
                        msg_type = "text" # 转为文本处理流程
                        
                        # 告诉前端识别结果，用于显示用户消息
                        await websocket.send_json({
                            "type": "user_input", 
                            "content": text
                        })
                    else:
                        await websocket.send_json({"type": "error", "content": "未能识别出语音"})
                        continue
                        
                except sr.UnknownValueError:
                    print("STT: UnknownValueError")
                    await websocket.send_json({"type": "error", "content": "听不清，请再说一遍"})
                    continue
                except sr.RequestError as e:
                    print(f"STT: RequestError {e}")
                    await websocket.send_json({"type": "error", "content": "语音服务连接失败，请检查网络"})
                    continue
                except Exception as e:
                    print(f"STT Error: {e}")
                    await websocket.send_json({"type": "error", "content": f"语音处理错误: {str(e)}"})
                    continue

            if not user_input and msg_type == "text":
                continue

            # 处理图片
            if msg_type == "image":
                try:
                    image_data_str = message_data.get("content", "")
                    mode = message_data.get("mode", "manual") # 'observer' or 'manual'
                    mime_type = "image/jpeg"
                    
                    if "base64," in image_data_str:
                        header, encoded = image_data_str.split("base64,", 1)
                        if "data:" in header and ";" in header:
                            mime_type = header.split("data:")[1].split(";")[0]
                        image_bytes = base64.b64decode(encoded)
                    else:
                        image_bytes = base64.b64decode(image_data_str)
                    
                    # [Observer Mode Logic]
                    if mode == "observer":
                        # 观察模式：静默分析，决定是否说话
                        current_time = asyncio.get_running_loop().time()
                        
                        # 获取游戏上下文 (Game Context)
                        # 前端如果选择了泰拉瑞亚模式，会传 {"name": "Terraria"}
                        # 如果没有传，默认是 General
                        game_context = message_data.get("game_context", {"name": "General"})
                        
                        # 1. 调用 Vision Service 分析 (Mode=observer)
                        # 注意：我们这里不进行前置冷却检查，而是先分析，再决策
                        # 这样可以保证 Soft Context 一直被更新
                        
                        # [Legacy] 这里的代码是旧的 observer 逻辑，已经被上面的 auto_observe 逻辑覆盖了
                        # 前端现在的实现是发送 type='auto_observe' 而不是 type='image' mode='observer'
                        # 但为了兼容性，我们把这里的逻辑也对齐一下
                        
                        analysis_result_json = vision_service.analyze_image(image_bytes, mode="observer", game_context=game_context)
                        
                        try:
                            clean_json = analysis_result_json.replace("```json", "").replace("```", "").strip()
                            analysis_data = json.loads(clean_json)
                            description = analysis_data.get("description", "")
                            category = analysis_data.get("category", "IGNORE")
                            
                            print(f"[Observer Legacy] Category: {category}, Desc: {description}")
                            
                            # 决策逻辑
                            current_ts = time.time()
                            observer_state.update_soft_context(description, current_ts)
                            should_speak = observer_state.should_speak(category, current_ts)
                            
                            if should_speak:
                                observer_state.record_speak(category, current_ts)
                                
                                # 构造输入
                                hints = [
                                    "（请进行极简短的互动，表示你在陪着我，不要长篇大论）",
                                    "（请用好奇的语气问我在做什么，只说一句话）"
                                ]
                                import random
                                interaction_hint = random.choice(hints) if category == "SOFTSPEAK" else "（请根据画面内容进行吐槽或情绪共鸣，语气自然一点）"
                                
                                observe_input = f"【系统视觉观察】用户屏幕当前显示：{description}。{interaction_hint}"
                                
                                # 借用 agent.chat 生成回复
                                full_response = ""
                                for chunk in agent.chat(observe_input, allow_behavior_memory=True, allow_l0=True):
                                    full_response += chunk
                                    await websocket.send_json({
                                        "type": "chunk",
                                        "content": chunk,
                                        "is_final": False
                                    })
                                    await asyncio.sleep(0.01)
                                    
                            else:
                                if category != "IGNORE":
                                    agent.add_observation_to_context(description)
                                    print(f"[Observer Legacy] Silent observation recorded (Category: {category})")
                                continue
                                
                        except Exception as e:
                            print(f"[Observer Legacy] Error: {str(e)}")
                            continue
                            
                    else:
                        # 手动模式：总是回复
                        full_response = ""
                        for chunk in agent.process_image(image_bytes, mime_type, allow_behavior_memory=allow_behavior_memory, allow_l0=allow_l0):
                            full_response += chunk
                            await websocket.send_json({
                                "type": "chunk",
                                "content": chunk,
                                "is_final": False
                            })
                            await asyncio.sleep(0.01)
                        
                    await websocket.send_json({
                        "type": "done",
                        "content": "",
                        "is_final": True
                    })
                    
                except Exception as e:
                    error_msg = f"Image Error: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "content": error_msg
                    })

            # 处理文本对话
            elif msg_type == "text":
                # 流式回复 + TTS 分句缓冲
                full_response = ""
                tts_buffer = ""
                tts_queue = asyncio.Queue()
                
                # 启动 TTS 消费者任务 (Single Worker)
                tts_task = asyncio.create_task(tts_worker(websocket, tts_queue, tts_service))

                # 优化分句正则：更细粒度的切分，支持逗号、分号，但保留句子结构
                # 匹配：句号、问号、感叹号、换行符、逗号、分号
                sentence_endings = re.compile(r'(?<!\.)[.!?。？！\n,，;；]+')
                
                # 最小切分长度阈值 (防止切太碎)
                MIN_SENTENCE_LENGTH = 8

                try:
                    chunk_id = 0
                    for chunk in agent.chat(user_input, allow_behavior_memory=allow_behavior_memory, allow_l0=allow_l0):
                        full_response += chunk
                        tts_buffer += chunk
                        
                        # 发送文本块给前端
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                            "is_final": False
                        })

                        # TTS 生产者逻辑
                        if enable_tts:
                            # 1. 尝试寻找切分点
                            match = sentence_endings.search(tts_buffer)
                            if match:
                                # 找到结束符
                                end_pos = match.end()
                                raw_sentence = tts_buffer[:end_pos].strip()
                                
                                # 2. 智能合并策略
                                # 只有当 当前句子长度 >= 阈值，或者 缓冲区太长了，才切分
                                # 否则继续积攒，直到下一个标点或结束
                                if len(raw_sentence) >= MIN_SENTENCE_LENGTH or len(tts_buffer) > 50:
                                    tts_buffer = tts_buffer[end_pos:] # 剩余部分留给下一次
                                    
                                    # 清洗文本
                                    clean_sentence = sanitize_text_for_tts(raw_sentence)
                                    
                                    if clean_sentence:
                                        # 放入队列，生产者不等待
                                        await tts_queue.put((chunk_id, clean_sentence))
                                        chunk_id += 1
                                else:
                                    # 还没到阈值，继续攒着
                                    pass

                        await asyncio.sleep(0.01)
                    
                    # 循环结束后，处理剩余的 buffer
                    if enable_tts and tts_buffer.strip():
                        raw_sentence = tts_buffer.strip()
                        clean_sentence = sanitize_text_for_tts(raw_sentence)
                        if clean_sentence:
                            await tts_queue.put((chunk_id, clean_sentence))
                            chunk_id += 1
                    
                    # 发送哨兵，通知 Worker 结束
                    if enable_tts:
                        await tts_queue.put(None)
                        # 等待 TTS 任务全部完成
                        await tts_task

                    # 发送结束标记
                    await websocket.send_json({
                        "type": "done",
                        "content": "",
                        "is_final": True
                    })
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    print(error_msg)
                    await websocket.send_json({
                        "type": "error",
                        "content": error_msg
                    })
                    # 确保取消后台任务
                    if 'tts_task' in locals() and not tts_task.done():
                        tts_task.cancel()
                        
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # 确保取消后台任务 (双重保险)
        pass

# TTS 消费者 Worker
async def tts_worker(websocket: WebSocket, queue: asyncio.Queue, service: TTSService):
    """
    单线程消费 TTS 任务队列，确保 GPU 不过载
    """
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break
            
        chunk_id, text = item
        try:
            # 串行调用 TTS (耗时操作)
            audio_base64 = await service.text_to_speech(text)
            
            if audio_base64:
                await websocket.send_json({
                    "type": "audio_stream", # 新类型，支持流式
                    "sequence_id": chunk_id,
                    "content": audio_base64
                })
        except Exception as e:
            error_msg = f"TTS Worker Error: {str(e)}"
            print(error_msg)
            try:
                await websocket.send_json({
                    "type": "error",
                    "content": "语音生成失败，请检查 TTS 服务连接"
                })
            except:
                pass # 如果 websocket 断了就不管了
        finally:
            queue.task_done()
                    
@app.get("/health")
def health_check():
    return {"status": "ok", "model": config.PRIMARY_MODEL_NAME}

# [关键修正] 必须在所有 API 路由定义完成后，最后挂载静态文件到根路径
# 否则静态文件中间件会拦截掉 WebSocket 握手请求，导致 500 错误
try:
    app.mount("/", StaticFiles(directory="desktop-app", html=True), name="static")
except Exception as e:
    print(f"Warning: Failed to mount frontend static files: {e}")

if __name__ == "__main__":
    # 开发模式下运行
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
