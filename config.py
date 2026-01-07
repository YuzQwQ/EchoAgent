import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

def load_system_prompt():
    """从文件加载 System Prompt"""
    try:
        prompt_path = os.path.join(os.getcwd(), "core", "system_prompt.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        print(f"Warning: Failed to load system_prompt.md: {e}")
    
    # 回退机制
    return os.getenv("SYSTEM_PROMPT", "You are Echo, a helpful AI assistant.")

class Config:
    # LLM 设置
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    
    # 记忆设置
    HISTORY_FILE = os.path.join(os.getcwd(), "conversation.json")
    MAX_HISTORY_ROUNDS = int(os.getenv("MAX_HISTORY_ROUNDS", 10))
    
    # 动态加载 System Prompt
    SYSTEM_PROMPT = load_system_prompt()

    # UI 设置
    APP_TITLE = "Echo - AI Assistant MVP"
    USER_AVATAR = "👤"  # 使用 Emoji
    ECHO_AVATAR = "🤖"  # 使用 Emoji

config = Config()
