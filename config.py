import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(override=True)

def load_system_prompt():
    """从文件加载 System Prompt"""
    try:
        prompt_path = os.path.join(os.getcwd(), "core", "system_prompt.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                # print(f"DEBUG: Loaded System Prompt from {prompt_path} (Length: {len(content)})")
                return content
    except Exception as e:
        print(f"Warning: Failed to load system_prompt.md: {e}")
    
    # 回退机制
    return os.getenv("SYSTEM_PROMPT", "You are Echo, a helpful AI assistant.")

class Config:
    # --- Primary Model (Chat) ---
    # 优先读取 PRIMARY_ 前缀，回退到旧的 LLM_ 前缀以保持兼容（如果有旧配置残留）
    PRIMARY_API_KEY = os.getenv("PRIMARY_MODEL_API_KEY") or os.getenv("LLM_API_KEY", "")
    PRIMARY_BASE_URL = os.getenv("PRIMARY_MODEL_BASE_URL") or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    PRIMARY_MODEL_NAME = os.getenv("PRIMARY_MODEL") or os.getenv("LLM_MODEL", "gpt-3.5-turbo")

    # 兼容旧代码的别名
    LLM_API_KEY = PRIMARY_API_KEY
    LLM_BASE_URL = PRIMARY_BASE_URL
    LLM_MODEL = PRIMARY_MODEL_NAME

    # Vision Model Config
    VISION_MODEL_API_KEY = os.getenv("VISION_MODEL_API_KEY", os.getenv("DASHSCOPE_API_KEY"))
    VISION_MODEL_BASE_URL = os.getenv("VISION_MODEL_BASE_URL", "https://api.siliconflow.cn/v1")
    VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vl-max")

    # TTS Config
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge") # edge, gpt-sovits
    
    # Edge TTS Config
    EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoyiNeural")

    # GPT-SoVITS Config
    GPT_SOVITS_URL = os.getenv("GPT_SOVITS_URL", "http://127.0.0.1:9880/tts")

    # Agent Config记忆设置
    HISTORY_FILE = os.path.join(os.getcwd(), "conversation.json")
    MAX_HISTORY_ROUNDS = int(os.getenv("MAX_HISTORY_ROUNDS", 10))
    
    # 动态加载 System Prompt
    SYSTEM_PROMPT = load_system_prompt()

    # UI 设置
    APP_TITLE = "Echo - AI Assistant MVP"
    USER_AVATAR = "👤"  # 使用 Emoji
    ECHO_AVATAR = "🤖"  # 使用 Emoji

config = Config()
