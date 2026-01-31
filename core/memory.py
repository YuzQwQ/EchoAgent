import json
import os
from typing import List, Dict, Any, Optional
from config import config, load_system_prompt

class MemoryManager:
    def __init__(self, file_path: str = config.HISTORY_FILE):
        self.file_path = file_path
        self._ensure_file_exists()

    def _default_data(self) -> Dict[str, Any]:
        return {
            "summary": "",
            "messages": [],
            "behavior_fragments": [],
            "memory_layers": {
                "L0_observe": [],
                "L1_behavior": [],
                "L2_context": [],
                "L3_knowledge": [],
                "L4_profile": []
            },
            "memory_meta": {
                "cooldown": {
                    "last_ref_id": "",
                    "last_ref_turn": 0
                },
                "turn": 0
            }
        }

    def _ensure_file_exists(self):
        """确保存储文件存在"""
        if not os.path.exists(self.file_path):
            self.save_data(self._default_data())

    def load_data(self) -> Dict[str, Any]:
        """加载完整数据（包含 summary 和 messages）"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 兼容旧版本：如果是 list，转换成 dict
                if isinstance(data, list):
                    base = self._default_data()
                    base["messages"] = data
                    return base
                
                # 确保字段存在
                if "summary" not in data:
                    data["summary"] = ""
                if "messages" not in data:
                    data["messages"] = []
                if "behavior_fragments" not in data:
                    data["behavior_fragments"] = []
                if "memory_layers" not in data:
                    data["memory_layers"] = self._default_data()["memory_layers"]
                if "memory_meta" not in data:
                    data["memory_meta"] = self._default_data()["memory_meta"]
                if "cooldown" not in data["memory_meta"]:
                    data["memory_meta"]["cooldown"] = self._default_data()["memory_meta"]["cooldown"]
                if "turn" not in data["memory_meta"]:
                    data["memory_meta"]["turn"] = 0
                if data["behavior_fragments"] and not data["memory_layers"]["L1_behavior"]:
                    data["memory_layers"]["L1_behavior"] = data["behavior_fragments"]
                    
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return self._default_data()

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

    def add_behavior_fragment(self, fragment: Dict[str, str], max_items: int = 20):
        self.add_l1_fragment(fragment, max_items=max_items)

    def get_behavior_fragments(self) -> List[Dict[str, str]]:
        return self.get_l1()

    def add_l0_observation(self, observation: Dict[str, Any], max_items: int = 60):
        data = self.load_data()
        layer = data["memory_layers"]["L0_observe"]
        layer.append(observation)
        if len(layer) > max_items:
            layer[:] = layer[-max_items:]
        self.save_data(data)

    def get_l0(self) -> List[Dict[str, Any]]:
        data = self.load_data()
        return data["memory_layers"]["L0_observe"]

    def pop_l0_tail(self, count: int) -> List[Dict[str, Any]]:
        data = self.load_data()
        layer = data["memory_layers"]["L0_observe"]
        if count <= 0:
            return []
        removed = layer[-count:] if len(layer) >= count else layer[:]
        data["memory_layers"]["L0_observe"] = layer[:-count] if len(layer) > count else []
        self.save_data(data)
        return removed

    def add_l1_fragment(self, fragment: Dict[str, Any], max_items: int = 20):
        data = self.load_data()
        layer = data["memory_layers"]["L1_behavior"]
        layer.append(fragment)
        if len(layer) > max_items:
            layer[:] = layer[-max_items:]
        data["behavior_fragments"] = layer
        self.save_data(data)

    def get_l1(self) -> List[Dict[str, Any]]:
        data = self.load_data()
        return data["memory_layers"]["L1_behavior"]

    def add_l2_event(self, event: Dict[str, Any], max_items: int = 50):
        data = self.load_data()
        layer = data["memory_layers"]["L2_context"]
        layer.append(event)
        if len(layer) > max_items:
            layer[:] = layer[-max_items:]
        self.save_data(data)

    def get_l2(self) -> List[Dict[str, Any]]:
        data = self.load_data()
        return data["memory_layers"]["L2_context"]

    def increment_turn(self) -> int:
        data = self.load_data()
        data["memory_meta"]["turn"] = data["memory_meta"].get("turn", 0) + 1
        self.save_data(data)
        return data["memory_meta"]["turn"]

    def get_turn(self) -> int:
        data = self.load_data()
        return data["memory_meta"].get("turn", 0)

    def update_cooldown(self, ref_id: str, turn: int):
        data = self.load_data()
        data["memory_meta"]["cooldown"]["last_ref_id"] = ref_id
        data["memory_meta"]["cooldown"]["last_ref_turn"] = turn
        self.save_data(data)

    def get_cooldown(self) -> Dict[str, Any]:
        data = self.load_data()
        return data["memory_meta"].get("cooldown", {"last_ref_id": "", "last_ref_turn": 0})

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
        
        # 1. System Prompt (动态加载，支持热更新)
        context.append({"role": "system", "content": load_system_prompt()})
        
        # 2. Summary (如果存在)
        if summary:
            summary_prompt = f"【前情提要】\n之前的对话摘要：{summary}\n（请基于此背景继续对话，但不要重复摘要内容）"
            context.append({"role": "system", "content": summary_prompt})
            
        # 3. Recent Messages
        context.extend(messages)
        
        return context

    def clear_history(self):
        """清空所有历史和摘要"""
        self.save_data(self._default_data())
