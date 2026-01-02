import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Config:
    # LLM 设置
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    
    # 记忆设置
    HISTORY_FILE = os.path.join(os.getcwd(), "conversation.json")
    MAX_HISTORY_ROUNDS = int(os.getenv("MAX_HISTORY_ROUNDS", 10))
    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are Echo, a helpful AI assistant.")

    # UI 设置
    APP_TITLE = "Echo - AI Assistant MVP"
    USER_AVATAR = "👤"  # 使用 Emoji
    ECHO_AVATAR = "🤖"  # 使用 Emoji

config = Config()
