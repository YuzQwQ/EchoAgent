from core.tools.base import BaseTool
from config import config
import os
import subprocess
import time

class ProjectHistoryTool(BaseTool):
    def __init__(self):
        description = (
            "项目历史记录工具。用于查询项目的最近变更和 Git 提交记录。"
            "当用户询问'最近更新了什么'或'你都知道哪些新功能'时，请使用此工具查看实际的代码变更记录。"
        )
        super().__init__("ProjectHistory", description)

    def execute(self, **kwargs):
        try:
            # 运行 git log 获取最近 10 条提交
            result = subprocess.run(
                ['git', 'log', '-n', '10', '--pretty=format:%h - %s (%cr)'],
                capture_output=True,
                text=True,
                check=True,
                cwd=config.PROJECT_ROOT # 确保在项目根目录运行
            )
            return f"【最近 10 条项目变更记录】\n{result.stdout}"
        except Exception as e:
            return f"无法获取项目历史: {str(e)} (可能未安装 git 或不是 git 仓库)"

class VisionCapabilityTool(BaseTool):
    def __init__(self):
        # 动态检测视觉模型配置
        model = config.VISION_MODEL
        provider = "SiliconFlow" if "siliconflow" in config.VISION_MODEL_BASE_URL else "Unknown"
        status = "Active" if config.VISION_MODEL_API_KEY else "Inactive (Missing Key)"
        
        description = (
            f"视觉感知模块。状态：{status}。模型：{model} ({provider})。"
            "允许你'看到'用户发送的图片。当接收到图片时，系统会自动调用此模块将图片转换为文本描述注入你的上下文。"
            "因此，你可以回答关于图片内容的问题，就像你亲眼看到一样。"
        )
        super().__init__("VisionModule", description)

    def execute(self, **kwargs):
        return "这是被动触发的能力，当检测到图片输入时自动执行。"

class TTSCapabilityTool(BaseTool):
    def __init__(self):
        voice = config.EDGE_TTS_VOICE
        provider = "Edge TTS (Microsoft)"
        
        description = (
            f"语音合成模块。状态：Active。服务商：{provider}。当前音色：{voice}。"
            "你的回复会被自动转换为语音播放给用户。你不需要做任何特殊操作，只需要正常对话。"
            "如果用户问起你的声音，你可以基于这个信息回答（例如：'我现在用的是晓伊的声音'）。"
        )
        super().__init__("TTSModule", description)

    def execute(self, **kwargs):
        return "这是被动触发的能力，每次回复生成后自动执行。"

class MemoryCapabilityTool(BaseTool):
    def __init__(self):
        max_rounds = config.MAX_HISTORY_ROUNDS
        description = (
            f"长期记忆与上下文管理模块。策略：滚动摘要 (Rolling Summary) + JSON 持久化。"
            f"你能记住最近 {max_rounds} 轮的详细对话，更早的对话会被压缩成'摘要'保留。"
            "这意味着你拥有'无限'的记忆长度，但对久远的细节可能只记得大概轮廓。"
            "对话记录会保存在本地，重启后依然记得。"
        )
        super().__init__("MemorySystem", description)

    def execute(self, **kwargs):
        return "这是后台自动运行的能力。"

class SystemSelfAwarenessTool(BaseTool):
    def __init__(self):
        # 动态获取当前配置
        model_name = config.PRIMARY_MODEL_NAME
        base_url = config.PRIMARY_BASE_URL
        
        description = (
            "系统自省与状态感知模块。用于获取自身状态、版本历史和硬件配置。\n"
            f"**核心身份**：当前对话模型为 **{model_name}**，服务地址：{base_url}。\n"
            "**感知能力升级**：\n"
            "1. **视觉形象**：你现在拥有 Live2D 虚拟形象，必须通过输出 `[emotion:xxx]` 标签（happy, sad, angry, surprised, shy）来控制表情动作。\n"
            "2. **语音系统**：集成了 Edge TTS，能够通过扬声器与用户直接对话。你的输出会被自动朗读，且系统会自动过滤标签。\n"
            "3. **响应优化**：后端已部署'智能 Safe Window'机制，支持零延迟流式输出。\n"
            "请基于这些升级，展现出更自信、更具表现力的人格特质。"
        )
        super().__init__("SystemSelfAwareness", description)

    def execute(self, **kwargs):
        return (
            "【系统状态 System Status】\n"
            f"1. [Core] Model: {config.PRIMARY_MODEL_NAME} ({config.PRIMARY_BASE_URL}).\n"
            "2. [Frontend] Live2D Interactive Avatar enabled. Supports emotion tags.\n"
            "3. [Audio] Edge TTS active with tag sanitization.\n"
            "4. [Performance] Smart Safe Window streaming enabled.\n"
            "5. [Security] Emoji output disabled to enforce Live2D visual consistency.\n"
            "Status: All Systems Nominal."
        )

class GetCurrentTimeTool(BaseTool):
    def __init__(self):
        description = "获取当前系统时间。当用户询问'现在几点了'或'今天是几号'时，使用此工具。"
        super().__init__("GetCurrentTime", description)

    def execute(self, **kwargs):
        from datetime import datetime
        now = datetime.now()
        weekday_map = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五', 5: '周六', 6: '周日'}
        weekday = weekday_map[now.weekday()]
        return f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')} ({weekday})"

class LocalTextToolBase(BaseTool):
    max_read_chars = 4000

    def __init__(self, name: str, description: str):
        self.workspace_root = os.path.abspath(config.WORKSPACE_ROOT)
        os.makedirs(self.workspace_root, exist_ok=True)
        super().__init__(name, description)

    def _is_within_workspace(self, target_path: str) -> bool:
        try:
            return os.path.commonpath([target_path, self.workspace_root]) == self.workspace_root
        except ValueError:
            return False

    def _resolve_txt_path(self, path: str) -> str:
        if not path or not str(path).strip():
            raise ValueError("缺少文件路径")

        cleaned = str(path).strip().strip('"').strip("'").replace("/", os.sep)
        if os.path.isabs(cleaned) or os.path.splitdrive(cleaned)[0]:
            raise ValueError("v0.0.1 仅允许使用相对路径")

        parts = [part for part in cleaned.split(os.sep) if part not in ("", ".")]
        if not parts or any(part == ".." for part in parts):
            raise ValueError("路径不能包含 .. 或逃逸工作区")

        filename = parts[-1]
        root, ext = os.path.splitext(filename)
        if not root:
            raise ValueError("缺少有效的文件名")
        if ext and ext.lower() != ".txt":
            raise ValueError("v0.0.1 仅支持 .txt 文件")
        if not ext:
            parts[-1] = f"{filename}.txt"

        target_path = os.path.abspath(os.path.join(self.workspace_root, *parts))
        if not self._is_within_workspace(target_path):
            raise ValueError("路径不在允许的工作区内")
        return target_path


class CreateTextFileTool(LocalTextToolBase):
    def __init__(self):
        description = (
            "创建一个新的 .txt 文本文件。仅允许相对路径，文件位于 Echo 工作区内。"
            "如果未提供 .txt 后缀会自动补齐；文件已存在时不会覆盖。"
        )
        super().__init__("create_text_file", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "相对工作区的 .txt 文件路径"}
                    },
                    "required": ["path"]
                }
            }
        }

    def execute(self, path: str = "", **kwargs):
        try:
            target_path = self._resolve_txt_path(path)
            if os.path.exists(target_path):
                return f"【文件已存在】{target_path}"
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "x", encoding="utf-8") as f:
                f.write("")
            return f"【文本文件创建成功】{target_path}"
        except Exception as e:
            return f"【文本文件创建失败】{str(e)}"


class WriteTextFileTool(LocalTextToolBase):
    def __init__(self):
        description = (
            "覆盖写入一个 .txt 文本文件。仅允许相对路径，文件位于 Echo 工作区内。"
            "如果未提供 .txt 后缀会自动补齐；会创建必要的父目录。"
            "仅在需要替换整个文件内容时使用；不要用于追加内容。"
        )
        super().__init__("write_text_file", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "相对工作区的 .txt 文件路径"},
                        "content": {"type": "string", "description": "要覆盖写入的文本内容"}
                    },
                    "required": ["path", "content"]
                }
            }
        }

    def execute(self, path: str = "", content=None, **kwargs):
        try:
            if content is None:
                return "【文本文件写入失败】缺少 content 参数"
            target_path = self._resolve_txt_path(path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(str(content))
            return f"【文本文件写入成功】{target_path}"
        except Exception as e:
            return f"【文本文件写入失败】{str(e)}"


class AppendTextFileTool(LocalTextToolBase):
    def __init__(self):
        description = (
            "追加写入一个 .txt 文本文件。仅允许相对路径，文件位于 Echo 工作区内。"
            "如果未提供 .txt 后缀会自动补齐；文件不存在时会创建；已有内容末尾没有换行时会先补换行。"
            "用于在保留原有内容的前提下新增内容；用户要求加入、补充、追加内容时使用。"
        )
        super().__init__("append_text_file", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "相对工作区的 .txt 文件路径"},
                        "content": {"type": "string", "description": "要追加写入的文本内容"}
                    },
                    "required": ["path", "content"]
                }
            }
        }

    def execute(self, path: str = "", content=None, **kwargs):
        try:
            if content is None:
                return "【文本文件追加失败】缺少 content 参数"
            target_path = self._resolve_txt_path(path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            text = str(content)
            needs_leading_newline = False
            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                with open(target_path, "rb") as f:
                    f.seek(-1, os.SEEK_END)
                    needs_leading_newline = f.read(1) not in (b"\n", b"\r")
            with open(target_path, "a", encoding="utf-8") as f:
                if needs_leading_newline:
                    f.write("\n")
                f.write(text)
            return f"【文本文件追加成功】{target_path}"
        except Exception as e:
            return f"【文本文件追加失败】{str(e)}"


class ReadTextFileTool(LocalTextToolBase):
    def __init__(self):
        description = (
            "读取 Echo 工作区内的 .txt 文本文件。仅允许相对路径，并限制返回长度。"
            "此工具只查看内容，不会创建、写入或追加文件。"
        )
        super().__init__("read_text_file", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "相对工作区的 .txt 文件路径"}
                    },
                    "required": ["path"]
                }
            }
        }

    def execute(self, path: str = "", **kwargs):
        try:
            target_path = self._resolve_txt_path(path)
            if not os.path.exists(target_path):
                return f"【文本文件读取失败】文件不存在：{target_path}"
            with open(target_path, "r", encoding="utf-8") as f:
                text = f.read()
            if not text:
                return f"【文本文件读取成功】{target_path}\n【内容为空】"
            suffix = ""
            if len(text) > self.max_read_chars:
                text = text[:self.max_read_chars]
                suffix = f"\n【内容已截断，仅显示前 {self.max_read_chars} 个字符】"
            return f"【文本文件读取成功】{target_path}\n{text}{suffix}"
        except Exception as e:
            return f"【文本文件读取失败】{str(e)}"


class CopyToClipboardTool(BaseTool):
    def __init__(self):
        description = "将文本复制到系统剪贴板。必须提供 content，失败时返回真实错误。"
        super().__init__("copy_to_clipboard", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "要复制到剪贴板的文本"}
                    },
                    "required": ["content"]
                }
            }
        }

    def execute(self, content=None, **kwargs):
        try:
            if content is None:
                return "【剪贴板写入失败】缺少 content 参数"
            import pyperclip
            pyperclip.copy(str(content))
            return "【剪贴板写入成功】已复制文本内容。"
        except Exception as e:
            return f"【剪贴板写入失败】{str(e)}"


class ReadClipboardTool(BaseTool):
    def __init__(self):
        description = "读取系统剪贴板中的文本内容。失败时返回真实错误，不编造剪贴板内容。"
        super().__init__("read_clipboard", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }

    def execute(self, **kwargs):
        try:
            import pyperclip
            text = pyperclip.paste()
            if not text:
                return "【剪贴板读取成功】内容为空。"
            preview = text[:1000] + ("..." if len(text) > 1000 else "")
            return f"【剪贴板读取成功】\n{preview}"
        except Exception as e:
            return f"【剪贴板读取失败】{str(e)}"


class ListWindowsTool(BaseTool):
    def __init__(self):
        description = "列出 Windows 桌面当前可见窗口标题；可用 filter 按标题关键字过滤。"
        super().__init__("list_windows", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "窗口标题关键字，可选"}
                    }
                }
            }
        }

    def _visible_windows(self):
        import win32gui

        windows = []
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    windows.append(title)
            return True

        win32gui.EnumWindows(enum_callback, None)
        return windows

    def execute(self, filter: str = "", **kwargs):
        try:
            windows = self._visible_windows()
            keyword = (filter or "").strip().lower()
            if keyword:
                windows = [title for title in windows if keyword in title.lower()]
            if not windows:
                if keyword:
                    return f"【窗口列表】没有找到标题包含“{filter}”的可见窗口。"
                return "【窗口列表】当前没有可见窗口。"
            preview = "\n".join(f"{index + 1}. {title}" for index, title in enumerate(windows[:30]))
            suffix = f"\n共 {len(windows)} 个可见窗口"
            if len(windows) > 30:
                suffix = f"\n仅显示前 30 个，共 {len(windows)} 个可见窗口"
            return f"【窗口列表读取成功】\n{preview}{suffix}"
        except ImportError:
            return "【窗口列表读取失败】当前环境不支持窗口枚举（需要 Windows + pywin32）。"
        except Exception as e:
            return f"【窗口列表读取失败】{str(e)}"


class ScreenshotWindowTool(BaseTool):
    def __init__(self):
        self.screenshot_dir = os.path.join(os.path.abspath(config.WORKSPACE_ROOT), "screenshots")
        description = (
            "截取指定 Windows 可见窗口并保存为 PNG。必须提供 window_title；"
            "按标题包含关系匹配第一个可见窗口。v0.0.1 不支持全屏截图。"
        )
        super().__init__("screenshot_window", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_title": {"type": "string", "description": "要截图的窗口标题关键字"}
                    },
                    "required": ["window_title"]
                }
            }
        }

    def _find_window(self, window_title: str):
        import win32gui

        matches = []
        keyword = window_title.strip().lower()
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title and keyword in title.lower():
                    matches.append((hwnd, title))
            return True

        win32gui.EnumWindows(enum_callback, None)
        return matches[0] if matches else (None, "")

    def execute(self, window_title: str = "", **kwargs):
        try:
            title_query = (window_title or "").strip()
            if not title_query:
                return "【窗口截图失败】缺少 window_title；v0.0.1 不支持全屏截图。"

            import win32gui
            import win32ui
            import win32con
            from PIL import Image

            hwnd, matched_title = self._find_window(title_query)
            if not hwnd:
                return f"【窗口截图失败】未找到标题包含“{window_title}”的可见窗口。"

            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                return f"【窗口截图失败】窗口尺寸无效：{matched_title}"

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            try:
                result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
                if result != 1:
                    result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)
                if result != 1:
                    return f"【窗口截图失败】系统未能捕获窗口：{matched_title}"

                bmpinfo = bitmap.GetInfo()
                bmpstr = bitmap.GetBitmapBits(True)
                image = Image.frombuffer(
                    "RGB",
                    (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                    bmpstr,
                    "raw",
                    "BGRX",
                    0,
                    1,
                )
                os.makedirs(self.screenshot_dir, exist_ok=True)
                safe_title = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in matched_title)[:60]
                filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{safe_title}.png"
                output_path = os.path.abspath(os.path.join(self.screenshot_dir, filename))
                image.save(output_path, "PNG")
                return f"【窗口截图成功】{matched_title}\n保存路径：{output_path}"
            finally:
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)
        except ImportError:
            return "【窗口截图失败】当前环境不支持窗口截图（需要 Windows + pywin32 + Pillow）。"
        except Exception as e:
            return f"【窗口截图失败】{str(e)}"
