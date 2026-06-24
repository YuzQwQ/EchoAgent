import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

from config import config
from core.agent import EchoAgent
from core.tools.base import ToolRegistry
from core.tools.system_tools import (
    AppendTextFileTool,
    CopyToClipboardTool,
    CreateTextFileTool,
    ListWindowsTool,
    ReadClipboardTool,
    ReadTextFileTool,
    ScreenshotWindowTool,
    WriteTextFileTool,
)


class LocalTextToolTests(unittest.TestCase):
    def setUp(self):
        self.original_workspace = config.WORKSPACE_ROOT
        self.temp_dir = tempfile.mkdtemp()
        config.WORKSPACE_ROOT = self.temp_dir

    def tearDown(self):
        config.WORKSPACE_ROOT = self.original_workspace
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    class FakeMemory:
        def __init__(self):
            self.messages = []
            self.turn = 0

        def add_message(self, role, content):
            self.messages.append({"role": role, "content": content})

        def increment_turn(self):
            self.turn += 1

        def get_context(self):
            return list(self.messages)

        def get_turn(self):
            return self.turn

        def get_l0(self):
            return []

        def get_l1(self):
            return []

        def get_l2(self):
            return []

        def add_l2_event(self, *args, **kwargs):
            pass

        def update_cooldown(self, *args, **kwargs):
            pass

    class SequenceLLM:
        def __init__(self, responses):
            self.responses = list(responses)
            self.messages = []

        def chat_completion_with_tools(self, messages, *args, **kwargs):
            self.messages.append(list(messages))
            if self.responses:
                return self.responses.pop(0)
            return types.SimpleNamespace(content="")

    def _tool_call(self, name, arguments, call_id="call_1"):
        if not isinstance(arguments, str):
            import json
            arguments = json.dumps(arguments, ensure_ascii=False)
        function = types.SimpleNamespace(name=name, arguments=arguments)
        return types.SimpleNamespace(id=call_id, type="function", function=function)

    def _tool_response(self, name, arguments, call_id="call_1", content=None):
        return types.SimpleNamespace(
            content=content,
            tool_calls=[self._tool_call(name, arguments, call_id=call_id)]
        )

    def _make_agent(self, llm):
        agent = EchoAgent.__new__(EchoAgent)
        agent.llm = llm
        agent.memory = self.FakeMemory()
        agent.rag = None
        agent.l2_max_items = 50
        agent.tools = ToolRegistry()
        agent.tools.register(AppendTextFileTool())
        agent._run_async_summary = lambda: None
        return agent

    def test_create_write_read_txt_success(self):
        create_result = CreateTextFileTool().execute(path="notes/demo")
        self.assertIn("创建成功", create_result)
        target = os.path.join(self.temp_dir, "notes", "demo.txt")
        self.assertTrue(os.path.exists(target))

        write_result = WriteTextFileTool().execute(path="notes/demo.txt", content="hello echo")
        self.assertIn("写入成功", write_result)

        read_result = ReadTextFileTool().execute(path="notes/demo")
        self.assertIn("读取成功", read_result)
        self.assertIn("hello echo", read_result)

    def test_append_txt_success(self):
        target = os.path.join(self.temp_dir, "shopping.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("milk")

        append_result = AppendTextFileTool().execute(path="shopping.txt", content="apple\nbanana")
        self.assertIn("追加成功", append_result)

        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual("milk\napple\nbanana", f.read())

    def test_append_creates_missing_txt(self):
        append_result = AppendTextFileTool().execute(path="new-list", content="pear")
        self.assertIn("追加成功", append_result)

        target = os.path.join(self.temp_dir, "new-list.txt")
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual("pear", f.read())

    def test_create_existing_file_does_not_overwrite(self):
        target = os.path.join(self.temp_dir, "keep.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("original")

        result = CreateTextFileTool().execute(path="keep.txt")
        self.assertIn("文件已存在", result)
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual("original", f.read())

    def test_rejects_non_txt_traversal_and_absolute_paths(self):
        create_tool = CreateTextFileTool()
        self.assertIn("仅支持 .txt", create_tool.execute(path="bad.md"))
        self.assertIn("不能包含 ..", create_tool.execute(path="../escape.txt"))
        self.assertIn("仅允许使用相对路径", create_tool.execute(path=os.path.abspath("outside.txt")))
        self.assertIn("仅允许使用相对路径", create_tool.execute(path="C:drive-relative.txt"))

    def test_write_requires_content_argument(self):
        result = WriteTextFileTool().execute(path="missing-content.txt")
        self.assertIn("缺少 content", result)

    def test_write_rejects_legacy_new_content_argument(self):
        result = WriteTextFileTool().execute(path="legacy.txt", new_content="legacy body")
        self.assertIn("缺少 content", result)
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "legacy.txt")))


    def test_agent_text_response_does_not_trigger_tool(self):
        fake_llm = self.SequenceLLM([
            types.SimpleNamespace(content="编辑文本功能很蠢，我同意这个吐槽。")
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_calls([], "编辑文本功能很蠢")

        self.assertEqual(0, result["tool_calls"])
        self.assertEqual([], result["executed_tools"])
        self.assertIn("编辑文本功能很蠢", result["text_response"])
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "购物清单.txt")))
        tool_prompts = [
            msg["content"]
            for msg in fake_llm.messages[0]
            if msg.get("role") == "system" and "【工具选择规则】" in msg.get("content", "")
        ]
        self.assertEqual(1, len(tool_prompts))
        self.assertIn("append_text_file", tool_prompts[0])
        self.assertIn("不要用 read_text_file 代替 write_text_file 或 append_text_file", tool_prompts[0])

    def test_agent_executes_append_tool_call(self):
        target = os.path.join(self.temp_dir, "购物清单.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("苹果\n香蕉")

        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "购物清单.txt", "content": "梨"}),
            types.SimpleNamespace(content="已追加到购物清单.txt")
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_calls([], "在购物清单加入梨")

        self.assertEqual(1, result["tool_calls"])
        self.assertIn("已追加到购物清单.txt", result["text_response"])
        self.assertIn("追加成功", str(result["executed_tools"][0]["result"]))
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual("苹果\n香蕉\n梨", f.read())

    def test_agent_reports_unknown_tool_without_aliasing(self):
        target = os.path.join(self.temp_dir, "购物清单.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("苹果\n香蕉")

        fake_llm = self.SequenceLLM([
            self._tool_response("append_file", {"path": "购物清单.txt", "content": "梨"}),
            types.SimpleNamespace(content="工具名不对，应该用 append_text_file。")
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_calls([], "在购物清单加入梨")

        self.assertEqual(1, result["tool_calls"])
        self.assertIn("不存在", str(result["executed_tools"][0]["result"]))
        self.assertIn("append_text_file", str(result["executed_tools"][0]["result"]))
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual("苹果\n香蕉", f.read())

    def test_agent_reports_missing_append_content(self):
        target = os.path.join(self.temp_dir, "购物清单.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("苹果\n香蕉")

        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "购物清单.txt"}),
            types.SimpleNamespace(content="没写进去，缺少要追加的内容。")
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_calls([], "在购物清单加入梨")

        self.assertEqual(1, result["tool_calls"])
        self.assertIn("缺少 content", str(result["executed_tools"][0]["result"]))
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual("苹果\n香蕉", f.read())

    def test_agent_reports_invalid_tool_arguments(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", '{"path":"购物清单.txt",'),
            types.SimpleNamespace(content="参数格式不对，我没法写入。")
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_calls([], "在购物清单加入梨")

        self.assertEqual(1, result["tool_calls"])
        self.assertIn("Invalid tool arguments", str(result["executed_tools"][0]["result"]))
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "购物清单.txt")))

    def test_chat_returns_natural_reply_after_successful_tool_call(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "todo.txt", "content": "梨"}),
            types.SimpleNamespace(content="已追加到 todo.txt。")
        ])
        agent = self._make_agent(fake_llm)

        response = "".join(agent.chat("在 todo.txt 里追加梨"))

        self.assertEqual("已追加到 todo.txt。", response)
        self.assertNotIn("【文本文件追加成功】", response)
        self.assertNotIn('"ok"', response)
        with open(os.path.join(self.temp_dir, "todo.txt"), "r", encoding="utf-8") as f:
            self.assertEqual("梨", f.read())

    def test_chat_returns_natural_reply_after_tool_error(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "bad.md", "content": "梨"}),
            types.SimpleNamespace(content="没写进去，v0.0.1 只能处理 .txt 文件。")
        ])
        agent = self._make_agent(fake_llm)

        response = "".join(agent.chat("在 bad.md 里追加梨"))

        self.assertIn("只能处理 .txt", response)
        self.assertNotIn("【文本文件追加失败】", response)
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "bad.md")))

    def test_chat_without_tool_calls_returns_plain_text(self):
        fake_llm = self.SequenceLLM([
            types.SimpleNamespace(content="只是聊天，不动文件。")
        ])
        agent = self._make_agent(fake_llm)

        response = "".join(agent.chat("编辑文本功能很蠢"))

        self.assertEqual("只是聊天，不动文件。", response)
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "购物清单.txt")))

    def test_tool_loop_stops_at_max_rounds(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "loop.txt", "content": "x"}, call_id="call_1"),
            self._tool_response("append_text_file", {"path": "loop.txt", "content": "x"}, call_id="call_2"),
            self._tool_response("append_text_file", {"path": "loop.txt", "content": "x"}, call_id="call_3"),
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_loop([], max_tool_rounds=2)

        self.assertEqual(2, result["tool_calls"])
        self.assertEqual(2, len(result["executed_tools"]))
        self.assertIn("工具调用次数过多", result["text_response"])
        with open(os.path.join(self.temp_dir, "loop.txt"), "r", encoding="utf-8") as f:
            self.assertEqual("x\nx", f.read())

    def test_tool_messages_are_ordered_for_final_reply(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "order.txt", "content": "梨"}),
            types.SimpleNamespace(content="已追加。")
        ])
        agent = self._make_agent(fake_llm)

        result = agent._run_tool_loop([{"role": "user", "content": "追加梨"}])

        self.assertEqual(1, result["tool_calls"])
        final_messages = fake_llm.messages[-1]
        roles = [message["role"] for message in final_messages if message["role"] in ("user", "assistant", "tool")]
        self.assertEqual(["user", "assistant", "tool"], roles)
        tool_content = final_messages[-2]["content"]
        self.assertIn('"ok": true', tool_content)
        self.assertIn('"tool": "append_text_file"', tool_content)

    def test_chat_emits_trace_events_for_successful_tool_call(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "trace.txt", "content": "hello"}),
            types.SimpleNamespace(content="done")
        ])
        agent = self._make_agent(fake_llm)
        events = []

        response = "".join(agent.chat("append hello", event_sink=events.append))

        self.assertEqual("done", response)
        event_names = [event["event"] for event in events]
        self.assertIn("chat_start", event_names)
        self.assertIn("llm_request", event_names)
        self.assertIn("tool_call", event_names)
        self.assertIn("tool_result", event_names)
        self.assertIn("chat_end", event_names)

        tool_call = next(event for event in events if event["event"] == "tool_call")
        self.assertEqual("append_text_file", tool_call["tool"])
        self.assertEqual("append", tool_call["action"])

        tool_result = next(event for event in events if event["event"] == "tool_result")
        self.assertTrue(tool_result["ok"])
        self.assertEqual("append_text_file", tool_result["tool"])
        self.assertEqual("append", tool_result["action"])
        self.assertIn("trace.txt", tool_result.get("path", ""))

    def test_chat_emits_trace_events_for_tool_error(self):
        fake_llm = self.SequenceLLM([
            self._tool_response("append_text_file", {"path": "bad.md", "content": "hello"}),
            types.SimpleNamespace(content="failed")
        ])
        agent = self._make_agent(fake_llm)
        events = []

        response = "".join(agent.chat("append hello", event_sink=events.append))

        self.assertEqual("failed", response)
        tool_result = next(event for event in events if event["event"] == "tool_result")
        self.assertFalse(tool_result["ok"])
        self.assertEqual("error", tool_result["level"])
        self.assertIn("error_type", tool_result)
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "bad.md")))

    def test_chat_without_tool_calls_emits_chat_trace_only(self):
        fake_llm = self.SequenceLLM([
            types.SimpleNamespace(content="plain")
        ])
        agent = self._make_agent(fake_llm)
        events = []

        response = "".join(agent.chat("chat only", event_sink=events.append))

        self.assertEqual("plain", response)
        event_names = [event["event"] for event in events]
        self.assertIn("chat_start", event_names)
        self.assertIn("chat_end", event_names)
        self.assertNotIn("tool_call", event_names)
        self.assertNotIn("tool_result", event_names)

    def test_trace_sanitizer_redacts_secrets_and_truncates_payloads(self):
        agent = EchoAgent.__new__(EchoAgent)
        long_content = "x" * 700
        base64_content = "a" * 160
        payload = {
            "api_key": "secret-key",
            "authorization": "Bearer token",
            "content": long_content,
            "image": f"data:image/png;base64,{base64_content}",
            "nested": {"access_token": "nested-secret"}
        }

        sanitized = agent._sanitize_trace_value(payload)

        self.assertEqual("[redacted]", sanitized["api_key"])
        self.assertEqual("[redacted]", sanitized["authorization"])
        self.assertTrue(sanitized["content"].endswith("...[truncated]"))
        self.assertIn("[data-url omitted", sanitized["image"])
        self.assertEqual("[redacted]", sanitized["nested"]["access_token"])


class ClipboardToolTests(unittest.TestCase):
    def test_clipboard_read_write_uses_pyperclip(self):
        fake_pyperclip = types.SimpleNamespace(value="")

        def copy(value):
            fake_pyperclip.value = value

        def paste():
            return fake_pyperclip.value

        fake_pyperclip.copy = copy
        fake_pyperclip.paste = paste

        with mock.patch.dict(sys.modules, {"pyperclip": fake_pyperclip}):
            write_result = CopyToClipboardTool().execute(content="copied text")
            read_result = ReadClipboardTool().execute()

        self.assertIn("写入成功", write_result)
        self.assertIn("读取成功", read_result)
        self.assertIn("copied text", read_result)


class WindowToolTests(unittest.TestCase):
    def _raise_import_for_win32(self, name, *args, **kwargs):
        if name.startswith("win32"):
            raise ImportError("missing win32")
        return self.original_import(name, *args, **kwargs)

    def test_list_windows_reports_missing_pywin32(self):
        self.original_import = __import__
        with mock.patch("builtins.__import__", side_effect=self._raise_import_for_win32):
            result = ListWindowsTool().execute()
        self.assertIn("pywin32", result)

    def test_screenshot_window_reports_missing_pywin32(self):
        self.original_import = __import__
        with mock.patch("builtins.__import__", side_effect=self._raise_import_for_win32):
            result = ScreenshotWindowTool().execute(window_title="Notepad")
        self.assertIn("pywin32", result)

    def test_screenshot_window_requires_title(self):
        result = ScreenshotWindowTool().execute()
        self.assertIn("缺少 window_title", result)


if __name__ == "__main__":
    unittest.main()
