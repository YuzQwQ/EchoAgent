import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

from config import config
from core.tools.system_tools import (
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
