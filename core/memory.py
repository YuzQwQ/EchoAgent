import json
import os
from typing import List, Dict, Any, Optional
from config import config

class MemoryManager:
    def __init__(self, file_path: str = config.HISTORY_FILE):
        self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """确保存储文件存在"""
        if not os.path.exists(self.file_path):
            self.save_data({"summary": "", "messages": []})

    def load_data(self) -> Dict[str, Any]:
        """加载完整数据（包含 summary 和 messages）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 兼容旧版本：如果是 list，转换成 dict
                if isinstance(data, list):
                    return {"summary": "", "messages": data}
                
                # 确保字段存在
                if "summary" not in data:
                    data["summary"] = ""
                if "messages" not in data:
                    data["messages"] = []
                    
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return {"summary": "", "messages": []}

    def save_data(self, data: Dict[str, Any]):
        """保存完整数据"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def load_history(self) -> List[Dict[str, str]]:
        """获取消息列表（兼容旧接口）"""
        data = self.load_data()
        return data["messages"]
    
    def get_summary(self) -> str:
        """获取当前摘要"""
        data = self.load_data()
        return data.get("summary", "")

    def update_summary(self, new_summary: str):
        """更新摘要"""
        data = self.load_data()
        data["summary"] = new_summary
        self.save_data(data)

    def add_message(self, role: str, content: str):
        """添加一条新消息"""
        data = self.load_data()
        data["messages"].append({"role": role, "content": content})
        self.save_data(data)

    def pop_oldest_messages(self, count: int = 1) -> List[Dict[str, str]]:
        """移除并返回最早的几条消息（用于摘要）"""
        data = self.load_data()
        if len(data["messages"]) < count:
            return []
        
        removed = data["messages"][:count]
        data["messages"] = data["messages"][count:]
        self.save_data(data)
        return removed

    def get_context(self) -> List[Dict[str, str]]:
        """获取用于传给 LLM 的上下文"""
        data = self.load_data()
        messages = data["messages"]
        summary = data.get("summary", "")
        
        context = []
        
        # 1. System Prompt
        context.append({"role": "system", "content": config.SYSTEM_PROMPT})
        
        # 2. Summary (如果存在)
        if summary:
            summary_prompt = f"【前情提要】\n之前的对话摘要：{summary}\n（请基于此背景继续对话，但不要重复摘要内容）"
            context.append({"role": "system", "content": summary_prompt})
            
        # 3. Recent Messages
        context.extend(messages)
        
        return context

    def clear_history(self):
        """清空所有历史和摘要"""
        self.save_data({"summary": "", "messages": []})
