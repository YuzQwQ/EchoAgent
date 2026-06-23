import json
import os
import time
import threading
import atexit
import copy
from typing import List, Dict, Any
from config import config, load_system_prompt

class MemoryManager:
    def __init__(self, file_path: str | None = None):
        self.file_path = file_path or config.HISTORY_FILE
        self._legacy_file_path = config.LEGACY_HISTORY_FILE
        self._history_dir = os.path.dirname(self.file_path)
        self._max_files = config.HISTORY_MAX_FILES
        self._max_bytes = config.HISTORY_MAX_FILE_MB * 1024 * 1024
        self._cache_data = None
        self._dirty = False
        self._write_counter = 0
        self._last_flush = time.time()
        self._flush_every = 5
        self._flush_interval = 2.0
        self._lock = threading.Lock()
        self._migrate_legacy_history_if_needed()
        self._ensure_file_exists()
        atexit.register(self.flush)

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

    def _safe_load_json(self, path: str) -> Dict[str, Any] | None:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return self._normalize_data(json.load(f))
        except Exception:
            return None

    def _looks_empty(self, data: Dict[str, Any] | None) -> bool:
        if not data:
            return True
        if data.get("summary"):
            return False
        if data.get("messages"):
            return False
        memory_layers = data.get("memory_layers") or {}
        return not any(memory_layers.get(layer_name) for layer_name in memory_layers)

    def _migrate_legacy_history_if_needed(self):
        legacy_path = self._legacy_file_path
        if not legacy_path or os.path.abspath(legacy_path) == os.path.abspath(self.file_path):
            return
        if not os.path.exists(legacy_path):
            return

        current_data = self._safe_load_json(self.file_path) if os.path.exists(self.file_path) else None
        legacy_data = self._safe_load_json(legacy_path)
        if not legacy_data or not self._looks_empty(current_data):
            return

        if self._history_dir and not os.path.exists(self._history_dir):
            os.makedirs(self._history_dir, exist_ok=True)
        self._write_to_disk(legacy_data, allow_rotate=False)

    def _ensure_file_exists(self):
        """确保存储文件存在"""
        if self._history_dir and not os.path.exists(self._history_dir):
            os.makedirs(self._history_dir, exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write_to_disk(self._default_data(), allow_rotate=False)
        else:
            self._rotate_if_needed(self._load_from_disk())

    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        base = self._default_data()
        if isinstance(data, list):
            base["messages"] = data
            return base
        if "summary" not in data:
            data["summary"] = ""
        if "messages" not in data:
            data["messages"] = []
        if "behavior_fragments" not in data:
            data["behavior_fragments"] = []
        if "memory_layers" not in data:
            data["memory_layers"] = base["memory_layers"]
        if "memory_meta" not in data:
            data["memory_meta"] = base["memory_meta"]
        if "cooldown" not in data["memory_meta"]:
            data["memory_meta"]["cooldown"] = base["memory_meta"]["cooldown"]
        if "turn" not in data["memory_meta"]:
            data["memory_meta"]["turn"] = 0
        if data["behavior_fragments"] and not data["memory_layers"]["L1_behavior"]:
            data["memory_layers"]["L1_behavior"] = data["behavior_fragments"]
        return data

    def _load_from_disk(self) -> Dict[str, Any]:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return self._normalize_data(data)
        except (json.JSONDecodeError, FileNotFoundError):
            return self._default_data()

    def _write_to_disk(self, data: Dict[str, Any], allow_rotate: bool = True):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if allow_rotate:
                self._rotate_if_needed(data)
        except Exception as e:
            print(f"Error saving history: {e}")

    def _rotate_if_needed(self, data: Dict[str, Any]):
        if self._max_bytes <= 0:
            return
        try:
            if os.path.getsize(self.file_path) <= self._max_bytes:
                return
        except Exception:
            return
        self._archive_and_reset(data)

    def _archive_and_reset(self, data: Dict[str, Any]):
        base, ext = os.path.splitext(self.file_path)
        suffix = ext if ext else ".json"
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        archive_path = f"{base}.{timestamp}{suffix}"
        try:
            if os.path.exists(self.file_path):
                os.replace(self.file_path, archive_path)
        except Exception as e:
            print(f"Error archiving history: {e}")
        reduced = self._default_data()
        reduced["summary"] = data.get("summary", "")
        self._write_to_disk(reduced, allow_rotate=False)
        self._cache_data = reduced
        self._trim_archives()

    def _trim_archives(self):
        if self._max_files <= 0 or not self._history_dir or not os.path.isdir(self._history_dir):
            return
        base = os.path.basename(self.file_path)
        prefix = os.path.splitext(base)[0] + "."
        candidates = []
        for name in os.listdir(self._history_dir):
            if name == base:
                continue
            if name.startswith(prefix) and name.endswith(".json"):
                full = os.path.join(self._history_dir, name)
                try:
                    candidates.append((os.path.getmtime(full), full))
                except Exception:
                    continue
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _, path in candidates[self._max_files:]:
            try:
                os.remove(path)
            except Exception:
                continue

    def _maybe_flush(self):
        if not self._dirty:
            return
        now = time.time()
        if self._write_counter >= self._flush_every or (now - self._last_flush) >= self._flush_interval:
            self._write_to_disk(self._cache_data)
            self._dirty = False
            self._write_counter = 0
            self._last_flush = now

    def flush(self):
        with self._lock:
            if self._dirty and self._cache_data is not None:
                self._write_to_disk(self._cache_data)
                self._dirty = False
                self._write_counter = 0
                self._last_flush = time.time()

    def load_data(self) -> Dict[str, Any]:
        """加载完整数据（包含 summary 和 messages）"""
        with self._lock:
            if self._cache_data is None:
                self._cache_data = self._load_from_disk()
            return copy.deepcopy(self._cache_data)

    def save_data(self, data: Dict[str, Any], force: bool = False):
        """保存完整数据"""
        with self._lock:
            self._cache_data = data
            self._dirty = True
            self._write_counter += 1
            if force:
                self._write_to_disk(self._cache_data)
                self._dirty = False
                self._write_counter = 0
                self._last_flush = time.time()
            else:
                self._maybe_flush()

    def _mutate_data(self, fn, force: bool = False):
        with self._lock:
            if self._cache_data is None:
                self._cache_data = self._load_from_disk()
            fn(self._cache_data)
            self._dirty = True
            self._write_counter += 1
            if force:
                self._write_to_disk(self._cache_data)
                self._dirty = False
                self._write_counter = 0
                self._last_flush = time.time()
            else:
                self._maybe_flush()

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
        def mutate(data):
            data["summary"] = new_summary
        self._mutate_data(mutate, force=True)

    def add_message(self, role: str, content: str):
        """添加一条新消息"""
        def mutate(data):
            data["messages"].append({"role": role, "content": content})
        self._mutate_data(mutate)

    def add_behavior_fragment(self, fragment: Dict[str, str], max_items: int = 20):
        self.add_l1_fragment(fragment, max_items=max_items)

    def get_behavior_fragments(self) -> List[Dict[str, str]]:
        return self.get_l1()

    def add_l0_observation(self, observation: Dict[str, Any], max_items: int = 60):
        def mutate(data):
            layer = data["memory_layers"]["L0_observe"]
            layer.append(observation)
            if len(layer) > max_items:
                layer[:] = layer[-max_items:]
        self._mutate_data(mutate)

    def get_l0(self) -> List[Dict[str, Any]]:
        data = self.load_data()
        return data["memory_layers"]["L0_observe"]

    def pop_l0_tail(self, count: int) -> List[Dict[str, Any]]:
        if count <= 0:
            return []
        removed = []
        def mutate(data):
            nonlocal removed
            layer = data["memory_layers"]["L0_observe"]
            removed = layer[-count:] if len(layer) >= count else layer[:]
            data["memory_layers"]["L0_observe"] = layer[:-count] if len(layer) > count else []
        self._mutate_data(mutate)
        return removed

    def add_l1_fragment(self, fragment: Dict[str, Any], max_items: int = 20):
        def mutate(data):
            layer = data["memory_layers"]["L1_behavior"]
            layer.append(fragment)
            if len(layer) > max_items:
                layer[:] = layer[-max_items:]
            data["behavior_fragments"] = layer
        self._mutate_data(mutate)

    def get_l1(self) -> List[Dict[str, Any]]:
        data = self.load_data()
        return data["memory_layers"]["L1_behavior"]

    def add_l2_event(self, event: Dict[str, Any], max_items: int = 50):
        def mutate(data):
            layer = data["memory_layers"]["L2_context"]
            layer.append(event)
            if len(layer) > max_items:
                layer[:] = layer[-max_items:]
        self._mutate_data(mutate)

    def get_l2(self) -> List[Dict[str, Any]]:
        data = self.load_data()
        return data["memory_layers"]["L2_context"]

    def increment_turn(self) -> int:
        current_turn = 0
        def mutate(data):
            nonlocal current_turn
            data["memory_meta"]["turn"] = data["memory_meta"].get("turn", 0) + 1
            current_turn = data["memory_meta"]["turn"]
        self._mutate_data(mutate)
        return current_turn

    def get_turn(self) -> int:
        data = self.load_data()
        return data["memory_meta"].get("turn", 0)

    def update_cooldown(self, ref_id: str, turn: int):
        def mutate(data):
            data["memory_meta"]["cooldown"]["last_ref_id"] = ref_id
            data["memory_meta"]["cooldown"]["last_ref_turn"] = turn
        self._mutate_data(mutate)

    def get_cooldown(self) -> Dict[str, Any]:
        data = self.load_data()
        return data["memory_meta"].get("cooldown", {"last_ref_id": "", "last_ref_turn": 0})

    def pop_oldest_messages(self, count: int = 1) -> List[Dict[str, str]]:
        """移除并返回最早的几条消息（用于摘要）"""
        removed = []
        def mutate(data):
            nonlocal removed
            if len(data["messages"]) < count:
                removed = []
                return
            removed = data["messages"][:count]
            data["messages"] = data["messages"][count:]
        self._mutate_data(mutate)
        return removed

    def get_context(self) -> List[Dict[str, str]]:
        """获取用于传给 LLM 的上下文"""
        data = self.load_data()
        messages = data["messages"]
        summary = data.get("summary", "")
        
        context = []
        
        # 1. System Prompt
        context.append({"role": "system", "content": load_system_prompt()})
        
        # 2. Summary
        if summary:
            context.append({"role": "system", "content": f"【摘要】{summary}"})
            
        # 3. Recent Messages (Max 10 rounds = 20 msgs)
        # 如果消息太多，只取最近 N 条
        max_msgs = config.MAX_HISTORY_ROUNDS * 2
        recent_messages = messages[-max_msgs:] if len(messages) > max_msgs else messages
        
        context.extend(recent_messages)
        
        return context

    def clear_history(self):
        """清空所有历史和摘要"""
        self.save_data(self._default_data(), force=True)
