import json
import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 加载 .env 文件
load_dotenv(override=True)

RUNTIME_CONFIG_FILE = os.path.abspath(
    os.getenv("ECHO_RUNTIME_CONFIG_FILE", os.path.join(PROJECT_ROOT, ".echo_runtime_config.json"))
)


def load_runtime_config_file(path: str | None = None) -> dict:
    file_path = os.path.abspath(path or RUNTIME_CONFIG_FILE)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Warning: Failed to load runtime config: {e}")
        return {}


def save_runtime_config_values(values: dict, path: str | None = None) -> dict:
    file_path = os.path.abspath(path or config.RUNTIME_CONFIG_FILE)
    data = load_runtime_config_file(file_path)
    data.update(values)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    tmp_path = f"{file_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, file_path)
    return data


_PERSISTED_RUNTIME_CONFIG = load_runtime_config_file()


def _resolve_workspace_root() -> str:
    return (
        os.getenv("ECHO_WORKSPACE_ROOT")
        or _PERSISTED_RUNTIME_CONFIG.get("workspace_root")
        or os.getenv("ECHO_DEFAULT_WORKSPACE_ROOT")
        or os.path.join(PROJECT_ROOT, "_echo_workspace")
    )


def refresh_workspace_paths(workspace_root: str):
    root = os.path.abspath(os.path.expanduser(workspace_root))
    config.WORKSPACE_ROOT = root
    if os.getenv("HISTORY_DIR"):
        config.HISTORY_DIR = os.path.abspath(os.getenv("HISTORY_DIR", ""))
    else:
        config.HISTORY_DIR = os.path.abspath(os.path.join(root, "history"))
    config.HISTORY_FILE = (
        os.path.join(config.HISTORY_DIR, f"conversation_{config.HISTORY_SESSION_ID}.json")
        if config.HISTORY_SESSION_ID
        else os.path.join(root, "conversation.json")
    )
    return root

def load_system_prompt():
    """从文件加载 System Prompt"""
    try:
        candidate_paths = [
            os.path.join(PROJECT_ROOT, "core", "system_prompt.md"),
            os.path.join(os.getcwd(), "core", "system_prompt.md")
        ]
        for prompt_path in candidate_paths:
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    return content
    except Exception as e:
        print(f"Warning: Failed to load system_prompt.md: {e}")
    
    # 回退机制
    return os.getenv("SYSTEM_PROMPT", "You are Echo, a helpful AI assistant.")

class Config:
    PROJECT_ROOT = os.path.abspath(os.getenv("ECHO_PROJECT_ROOT", PROJECT_ROOT))
    RUNTIME_CONFIG_FILE = RUNTIME_CONFIG_FILE

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

    # Embedding Model Config
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY") or PRIMARY_API_KEY
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL") or PRIMARY_BASE_URL
    EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "text-embedding-3-small")

    # TTS Config
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge") # edge, gpt-sovits
    
    # Edge TTS Config
    EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoyiNeural")

    # GPT-SoVITS Config
    GPT_SOVITS_URL = os.getenv("GPT_SOVITS_URL", "http://127.0.0.1:9880/tts")

    WORKSPACE_ROOT = os.path.abspath(os.path.expanduser(_resolve_workspace_root()))
    # Agent Config记忆设置
    HISTORY_DIR = os.path.abspath(
        os.getenv("HISTORY_DIR", os.path.join(WORKSPACE_ROOT, "history"))
    )
    HISTORY_SESSION_ID = os.getenv("HISTORY_SESSION_ID", os.getenv("ECHO_SESSION_ID", ""))
    HISTORY_MAX_FILES = int(os.getenv("HISTORY_MAX_FILES", 20))
    HISTORY_MAX_FILE_MB = int(os.getenv("HISTORY_MAX_FILE_MB", 8))
    HISTORY_FILE = (
        os.path.join(HISTORY_DIR, f"conversation_{HISTORY_SESSION_ID}.json")
        if HISTORY_SESSION_ID
        else os.path.join(WORKSPACE_ROOT, "conversation.json")
    )
    LEGACY_HISTORY_FILE = os.path.join(PROJECT_ROOT, "conversation.json")
    MAX_HISTORY_ROUNDS = int(os.getenv("MAX_HISTORY_ROUNDS", 10))

    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", 30))

    STT_PROVIDER = os.getenv("STT_PROVIDER", "google")
    STT_LANGUAGE = os.getenv("STT_LANGUAGE", "zh-CN")
    STT_API_KEY = os.getenv("STT_API_KEY", PRIMARY_API_KEY)
    STT_BASE_URL = os.getenv("STT_BASE_URL", PRIMARY_BASE_URL)
    STT_OPENAI_MODEL = os.getenv("STT_OPENAI_MODEL", "whisper-1")
    
    # 动态加载 System Prompt
    SYSTEM_PROMPT = load_system_prompt()

    # UI 设置
    APP_TITLE = "Echo - AI Assistant MVP"
    USER_AVATAR = "👤"  # 使用 Emoji
    ECHO_AVATAR = "🤖"  # 使用 Emoji

config = Config()
