import json
import os
from typing import List, Dict, Any
from config import config

class MemoryManager:
    def __init__(self, file_path: str = config.HISTORY_FILE):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """确保存储文件存在，如果不存在则创建一个空列表"""
        if not os.path.exists(self.file_path):
            self.save_history([])

    def load_history(self) -> List[Dict[str, str]]:
        """加载对话历史"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if not isinstance(history, list):
                    return []
                return history
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_history(self, history: List[Dict[str, str]]):
        """保存对话历史"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def add_message(self, role: str, content: str):
        """添加一条新消息到历史记录"""
        history = self.load_history()
        history.append({"role": role, "content": content})
        
        # 简单的上下文修剪：保留最近的 N 轮对话 (N * 2 条消息)
        # 注意：这里假设 role 总是成对出现，实际可能需要更复杂的逻辑
        max_messages = config.MAX_HISTORY_ROUNDS * 2
        if len(history) > max_messages:
            # 保留 System prompt (如果有的话) 和最近的消息
            # 这里简单处理，直接切片保留最后 max_messages 条
            history = history[-max_messages:]
            
        self.save_history(history)

    def get_context(self) -> List[Dict[str, str]]:
        """获取用于传给 LLM 的上下文"""
        history = self.load_history()
        # 始终在开头添加 System Prompt
        system_message = {"role": "system", "content": config.SYSTEM_PROMPT}
        return [system_message] + history

    def clear_history(self):
        """清空历史"""
        self.save_history([])
