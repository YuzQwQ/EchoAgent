from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from core.agent import EchoAgent
from core.tts_service import TTSService
from core.vision_service import VisionService
from core.llm_service import LLMService
from config import config
from openai import OpenAI
import uvicorn
import asyncio
import json
import base64
import re
import os
import secrets
import speech_recognition as sr
import io
import cv2
import numpy as np
import time

app = FastAPI(title="Echo API Service")

def _get_allowed_origins():
    raw = os.getenv("ECHO_CORS_ORIGINS") or os.getenv("CORS_ALLOW_ORIGINS")
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [
        "http://127.0.0.1:18000",
        "http://localhost:18000",
        "null"
    ]

def _read_env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

ACCESS_TOKEN = (
    os.getenv("ECHO_ACCESS_TOKEN")
    or os.getenv("ECHO_API_TOKEN")
    or os.getenv("ACCESS_TOKEN")
)
ADMIN_TOKEN = os.getenv("ECHO_ADMIN_TOKEN") or os.getenv("ADMIN_TOKEN")
ALLOWED_ORIGINS = _get_allowed_origins()
PUBLIC_HEALTH = _read_env_flag("ECHO_PUBLIC_HEALTH", False)
PUBLIC_UI = _read_env_flag("ECHO_PUBLIC_UI", True)
WS_TICKET_TTL_SECONDS = int(os.getenv("ECHO_WS_TICKET_TTL_SECONDS", 60))
WS_TICKET_STORE: dict[str, float] = {}

def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    return host in ("127.0.0.1", "localhost", "::1") or host.startswith("127.")

def _is_loopback(request: Request) -> bool:
    if not request.client:
        return False
    return _is_loopback_host(request.client.host or "")

def _has_valid_access_token(token: str | None) -> bool:
    if token and ACCESS_TOKEN and token == ACCESS_TOKEN:
        return True
    if token and ADMIN_TOKEN and token == ADMIN_TOKEN:
        return True
    return False

def _has_valid_admin_token(token: str | None) -> bool:
    return bool(token and ADMIN_TOKEN and token == ADMIN_TOKEN)

def _prune_ws_tickets(now_ts: float | None = None):
    current = now_ts if now_ts is not None else time.time()
    expired = [ticket for ticket, expiry in WS_TICKET_STORE.items() if expiry <= current]
    for ticket in expired:
        WS_TICKET_STORE.pop(ticket, None)

def _issue_ws_ticket() -> tuple[str, int]:
    _prune_ws_tickets()
    ticket = secrets.token_urlsafe(24)
    expiry = time.time() + max(5, WS_TICKET_TTL_SECONDS)
    WS_TICKET_STORE[ticket] = expiry
    return ticket, int(expiry)

def _consume_ws_ticket(ticket: str | None) -> bool:
    if not ticket:
        return False
    _prune_ws_tickets()
    expiry = WS_TICKET_STORE.pop(ticket, None)
    if expiry is None:
        return False
    return expiry > time.time()

def _is_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True

    normalized = origin.strip().rstrip("/")
    if not normalized:
        return True
    if normalized == "null" or normalized.startswith("file://"):
        return True

    allowed = {item.strip().rstrip("/") for item in ALLOWED_ORIGINS if item.strip()}
    if "*" in allowed:
        return True
    return normalized in allowed

def _require_read_access(request: Request, access_token: str | None, admin_token: str | None):
    if ACCESS_TOKEN or ADMIN_TOKEN:
        if _has_valid_access_token(access_token) or _has_valid_admin_token(admin_token):
            return
        raise HTTPException(status_code=403, detail="Forbidden")
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="Forbidden")

def _require_write_access(request: Request, admin_token: str | None):
    if ADMIN_TOKEN:
        if not _has_valid_admin_token(admin_token):
            raise HTTPException(status_code=403, detail="Forbidden")
        return
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="Forbidden")

async def _require_websocket_access(websocket: WebSocket) -> bool:
    host = websocket.client.host if websocket.client else ""
    origin = websocket.headers.get("origin")
    query_ticket = websocket.query_params.get("ticket")
    query_access_token = websocket.query_params.get("access_token") or websocket.query_params.get("token")
    query_admin_token = websocket.query_params.get("admin_token")
    header_access_token = websocket.headers.get("x-access-token")
    header_admin_token = websocket.headers.get("x-admin-token")

    if not _is_origin_allowed(origin):
        await websocket.close(code=1008, reason="Forbidden origin")
        return False

    if ACCESS_TOKEN or ADMIN_TOKEN:
        if _consume_ws_ticket(query_ticket):
            return True
        if (
            _has_valid_access_token(query_access_token)
            or _has_valid_access_token(header_access_token)
            or _has_valid_admin_token(query_admin_token)
            or _has_valid_admin_token(header_admin_token)
        ):
            return True
        await websocket.close(code=1008, reason="Forbidden")
        return False

    if not _is_loopback_host(host):
        await websocket.close(code=1008, reason="Forbidden")
        return False

    return True

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    if not _is_origin_allowed(origin):
        return JSONResponse(status_code=403, content={"detail": "Forbidden origin"})

    path = request.url.path or "/"
    access_token = request.headers.get("x-access-token")
    admin_token = request.headers.get("x-admin-token")

    if path == "/health" and not PUBLIC_HEALTH:
        try:
            _require_read_access(request, access_token, admin_token)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    if (path == "/" or path.startswith("/ui")) and not PUBLIC_UI and not _is_loopback(request):
        return JSONResponse(status_code=403, content={"detail": "Remote UI disabled"})

    return await call_next(request)

# 初始化 Agent 和 TTS
agent = EchoAgent()
tts_service = TTSService()

def _transcribe_audio(audio_bytes: bytes) -> str:
    provider = (config.STT_PROVIDER or "google").lower()
    language = config.STT_LANGUAGE or "zh-CN"
    if provider == "google":
        r = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language=language)
    if provider in ("openai", "whisper"):
        if not config.STT_API_KEY:
            raise ValueError("Missing STT API Key")
        client = OpenAI(api_key=config.STT_API_KEY, base_url=config.STT_BASE_URL)
        result = client.audio.transcriptions.create(
            model=config.STT_OPENAI_MODEL,
            file=("audio.wav", audio_bytes, "audio/wav")
        )
        return result.text if hasattr(result, "text") else (result.get("text") if isinstance(result, dict) else "")
    raise ValueError(f"Unsupported STT provider: {provider}")

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
        """
        # 简单的活性衰减检查
        if current_time - self.soft_context["last_update"] > 600: # 10分钟无更新，重置
            self.soft_context["current_activity"] = ""
            self.soft_context["since"] = current_time
            self.soft_context["observation_count"] = 0
            
        self.soft_context["last_update"] = current_time
        self.soft_context["observation_count"] += 1
        
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

    def reset_cooldown(self):
        """重置冷却时间，通常在用户主动交互时调用"""
        self.last_speak_time = 0
        self.last_soft_speak_time = 0
        self.speak_history = []

    def should_speak(self, category: str, current_time: float) -> bool:
        if category == "IGNORE":
            return False

        if category == "NOTICE" or category == "SOFTSPEAK":
            if not self.check_speech_budget(current_time):
                return False

            if category == "SOFTSPEAK":
                import random
                if random.random() < 0.10:
                    return True
            return False

        if category == "SPEAK":
            if not self.check_speech_budget(current_time):
                return False
            return True

        return False

    def record_speak(self, category: str, current_time: float):
        self.speak_history.append(current_time)

        if category == "SPEAK":
            self.last_speak_time = current_time
        elif category == "SOFTSPEAK":
            self.last_soft_speak_time = current_time

class ObserverChangeDetector:
    def __init__(self):
        self.prev_gray = None
        self.stable_count = 0
        self.last_trigger_time = 0
        self.last_trigger_level = ""
        self.sustained_start = 0
        self.analysis_width = 160
        self.analysis_height = 90
        self.pixel_diff_threshold = 25
        self.change_light = 0.003
        self.change_medium = 0.01
        self.change_strong = 0.03
        self.stable_frames = 2
        self.min_interval = 2.5
        self.strong_min_interval = 0.8
        self.debounce = 1.5
        self.max_wait = 6.0

    def _decode_gray(self, image_bytes: bytes):
        arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        resized = cv2.resize(frame, (self.analysis_width, self.analysis_height), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        return gray

    def _level(self, change_ratio: float) -> str:
        if change_ratio >= self.change_strong:
            return "strong"
        if change_ratio >= self.change_medium:
            return "medium"
        if change_ratio >= self.change_light:
            return "light"
        return "idle"

    def should_trigger(self, image_bytes: bytes, now_ts: float) -> bool:
        gray = self._decode_gray(image_bytes)
        if gray is None:
            return True
        if self.prev_gray is None:
            self.prev_gray = gray
            return False
        diff = cv2.absdiff(gray, self.prev_gray)
        self.prev_gray = gray
        changed = np.count_nonzero(diff > self.pixel_diff_threshold)
        change_ratio = changed / diff.size
        level = self._level(change_ratio)

        if level == "idle":
            self.stable_count = 0
            self.sustained_start = 0
            return False

        if not self.sustained_start:
            self.sustained_start = now_ts

        if level in ["medium", "strong"]:
            self.stable_count += 1
        else:
            self.stable_count = 0

        debounced = self.last_trigger_level == level and (now_ts - self.last_trigger_time) < self.debounce

        if level == "strong" and (now_ts - self.last_trigger_time) >= self.strong_min_interval and not debounced:
            self.last_trigger_level = level
            self.last_trigger_time = now_ts
            self.stable_count = 0
            return True

        if self.stable_count >= self.stable_frames and (now_ts - self.last_trigger_time) >= self.min_interval and not debounced:
            self.last_trigger_level = level
            self.last_trigger_time = now_ts
            self.stable_count = 0
            return True

        if self.sustained_start and (now_ts - self.sustained_start) >= self.max_wait and (now_ts - self.last_trigger_time) >= self.min_interval:
            self.last_trigger_level = level
            self.last_trigger_time = now_ts
            self.stable_count = 0
            self.sustained_start = now_ts
            return True

        return False

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

vision_service = VisionService()


class RuntimeConfigUpdate(BaseModel):
    primary_api_key: str | None = None
    primary_base_url: str | None = None
    primary_model_name: str | None = None
    vision_api_key: str | None = None
    vision_base_url: str | None = None
    vision_model_name: str | None = None


def _apply_runtime_config(update: RuntimeConfigUpdate):
    """应用运行时模型配置，并重建相关服务实例。"""
    changed = []

    def set_if_present(value: str | None, attr_name: str, env_name: str):
        if value is None:
            return
        cleaned = value.strip()
        if cleaned == "":
            return
        setattr(config, attr_name, cleaned)
        os.environ[env_name] = cleaned
        changed.append(attr_name)

    set_if_present(update.primary_api_key, "PRIMARY_API_KEY", "PRIMARY_MODEL_API_KEY")
    set_if_present(update.primary_base_url, "PRIMARY_BASE_URL", "PRIMARY_MODEL_BASE_URL")
    set_if_present(update.primary_model_name, "PRIMARY_MODEL_NAME", "PRIMARY_MODEL")
    set_if_present(update.vision_api_key, "VISION_MODEL_API_KEY", "VISION_MODEL_API_KEY")
    set_if_present(update.vision_base_url, "VISION_MODEL_BASE_URL", "VISION_MODEL_BASE_URL")
    set_if_present(update.vision_model_name, "VISION_MODEL", "VISION_MODEL")

    # 兼容旧代码别名，保持 LLMService 与老调用路径一致
    config.LLM_API_KEY = config.PRIMARY_API_KEY
    config.LLM_BASE_URL = config.PRIMARY_BASE_URL
    config.LLM_MODEL = config.PRIMARY_MODEL_NAME

    if changed:
        # 仅重建受配置影响的服务，避免不必要的重启。
        agent.llm = LLMService()
        agent.vision = VisionService()
        global vision_service
        vision_service = VisionService()

    return changed

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    if not await _require_websocket_access(websocket):
        return
    await websocket.accept()
    print("WebSocket connected")
    change_detector = ObserverChangeDetector()
    
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
                    
                    current_ts = time.time()
                    if not change_detector.should_trigger(image_bytes, current_ts):
                        continue

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
                    
                    print("Recognizing speech...")
                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(None, lambda: _transcribe_audio(audio_bytes))
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
                except ValueError as e:
                    print(f"STT: ConfigError {e}")
                    await websocket.send_json({"type": "error", "content": "语音服务未配置或不可用"})
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
                        
                        game_context = message_data.get("game_context", {"name": "General"})
                        
                        # 1. 调用 Vision Service 分析 (Mode=observer)
                        # 注意：我们这里不进行前置冷却检查，而是先分析，再决策
                        # 这样可以保证 Soft Context 一直被更新
                        
                        if not change_detector.should_trigger(image_bytes, time.time()):
                            continue

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
                tts_queue: asyncio.Queue = asyncio.Queue()
                
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
            except Exception:
                return
        finally:
            queue.task_done()
                    
@app.get("/health")
def health_check():
    return {"status": "ok", "model": config.PRIMARY_MODEL_NAME}

@app.post("/auth/ws-ticket")
def issue_ws_ticket(
    request: Request,
    x_access_token: str | None = Header(default=None, alias="X-Access-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")
):
    _require_read_access(request, x_access_token, x_admin_token)
    ticket, expires_at = _issue_ws_ticket()
    return {
        "ok": True,
        "ticket": ticket,
        "expires_at": expires_at,
        "expires_in": max(5, WS_TICKET_TTL_SECONDS)
    }


@app.get("/runtime-config")
def get_runtime_config_status(
    request: Request,
    x_access_token: str | None = Header(default=None, alias="X-Access-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")
):
    _require_read_access(request, x_access_token, x_admin_token)
    return {
        "primary": {
            "base_url": config.PRIMARY_BASE_URL,
            "model": config.PRIMARY_MODEL_NAME,
            "api_key_set": bool(config.PRIMARY_API_KEY)
        },
        "vision": {
            "base_url": config.VISION_MODEL_BASE_URL,
            "model": config.VISION_MODEL,
            "api_key_set": bool(config.VISION_MODEL_API_KEY)
        }
    }


@app.post("/runtime-config")
def update_runtime_config(update: RuntimeConfigUpdate, request: Request, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    _require_write_access(request, x_admin_token)
    changed = _apply_runtime_config(update)
    return {
        "ok": True,
        "changed": changed,
        "active": {
            "primary_model": config.PRIMARY_MODEL_NAME,
            "vision_model": config.VISION_MODEL
        }
    }

try:
    app.mount("/ui", StaticFiles(directory="frontend", html=True), name="static")
except Exception as e:
    print(f"Warning: Failed to mount frontend static files: {e}")

@app.get("/")
async def root():
    return RedirectResponse(url="/ui/index.html")

if __name__ == "__main__":
    reload_enabled = os.getenv("ECHO_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run("api_server:app", host="0.0.0.0", port=18000, reload=reload_enabled)
