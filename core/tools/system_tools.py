from core.tools.base import BaseTool
from config import config
import os
import stat
import subprocess

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
                cwd=os.getcwd() # 确保在项目根目录运行
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

class ClipboardTool(BaseTool):
    def __init__(self):
        description = (
            "【系统剪贴板接口】\n"
            "必须使用此工具来与用户的剪贴板交互，严禁编造剪贴板内容。\n"
            "- 读取：当用户询问'剪贴板有什么'、'粘贴'、'看看剪贴板'时，必须调用 action='read'。\n"
            "- 写入：当用户要求'复制'、'写入剪贴板'时，必须调用 action='write' 并提供 content。"
        )
        super().__init__("Clipboard", description)

    def execute(self, action: str = "read", content: str = "", **kwargs):
        import pyperclip
        try:
            if action == "read":
                text = pyperclip.paste()
                if not text:
                    return "【剪贴板】内容为空。"
                # 截断过长内容，避免 Token 爆炸
                preview = text[:500] + "..." if len(text) > 500 else text
                return f"【剪贴板内容读取成功】\n{preview}"
            
            elif action == "write":
                if not content:
                    return "【错误】写入剪贴板需要提供 content 参数。"
                pyperclip.copy(content)
                return "【成功】已将内容写入系统剪贴板。"
            
            else:
                return f"【错误】不支持的操作类型：{action}。请使用 'read' 或 'write'。"
        except Exception as e:
            return f"【剪贴板操作失败】错误信息：{str(e)}"

class FileTool(BaseTool):
    def __init__(self):
        self.workspace_root = os.path.abspath(r"D:\develop\Echo\_echo_workspace")
        description = (
            "【文本文件读写工具】\n"
            f"仅允许在工作区内读写：{self.workspace_root}\n"
            "操作：read/write/append/create。read 读取文本；write 覆盖写入；append 追加写入；create 创建空文件。"
        )
        super().__init__("File", description)

    def to_dict(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "read/write/append/create"},
                        "path": {"type": "string", "description": "File path, absolute or relative to workspace"},
                        "content": {"type": "string", "description": "Text content for write/append"}
                    },
                    "required": ["action", "path"]
                }
            }
        }

    def _resolve_path(self, path: str) -> str:
        if not path:
            raise ValueError("缺少文件路径")
        cleaned = path.strip().strip('"').strip("'")
        if not os.path.isabs(cleaned):
            cleaned = os.path.join(self.workspace_root, cleaned)
        full_path = os.path.abspath(cleaned)
        if not os.path.isdir(self.workspace_root):
            raise ValueError(f"工作区不存在：{self.workspace_root}")
        if os.path.commonpath([full_path, self.workspace_root]) != self.workspace_root:
            raise ValueError("路径不在允许的工作区内")
        return full_path

    def _ensure_writable(self, target_path: str):
        try:
            os.chmod(self.workspace_root, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        except Exception:
            pass
        if os.path.exists(target_path):
            try:
                os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
        parent = os.path.dirname(target_path)
        if parent and os.path.isdir(parent):
            try:
                os.chmod(parent, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except Exception:
                pass

    def _fallback_path(self, target_path: str) -> str:
        fallback_dir = os.path.join(self.workspace_root, "_echo")
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            os.chmod(fallback_dir, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            return os.path.join(fallback_dir, os.path.basename(target_path))
        except Exception:
            secondary_root = os.path.join(os.getcwd(), "_echo_workspace")
            try:
                os.makedirs(secondary_root, exist_ok=True)
                os.chmod(secondary_root, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except Exception:
                pass
            return os.path.join(secondary_root, os.path.basename(target_path))

    def execute(self, action: str = "read", path: str = "", content: str = "", **kwargs):
        try:
            target_path = self._resolve_path(path)
            def _try_write_write(path_to_use: str, data: str, mode: str):
                try:
                    with open(path_to_use, mode, encoding="utf-8") as f:
                        f.write(data)
                    return None
                except PermissionError:
                    fb = self._fallback_path(path_to_use)
                    try:
                        os.makedirs(os.path.dirname(fb), exist_ok=True)
                        with open(fb, mode, encoding="utf-8") as f:
                            f.write(data)
                        return ("fallback", fb)
                    except Exception as e2:
                        return ("error", f"原路径：{path_to_use}，回退路径：{fb}，错误：{str(e2)}")
                except Exception as e:
                    return ("error", str(e))
            if action == "read":
                if not os.path.exists(target_path):
                    return f"【错误】文件不存在：{target_path}"
                with open(target_path, "r", encoding="utf-8") as f:
                    text = f.read()
                if not text:
                    return f"【文件读取成功】{target_path}\n【内容为空】"
                preview = text[:2000] + ("..." if len(text) > 2000 else "")
                return f"【文件读取成功】{target_path}\n{preview}"
            if action == "write":
                parent = os.path.dirname(target_path)
                if parent and not os.path.isdir(parent):
                    os.makedirs(parent, exist_ok=True)
                self._ensure_writable(target_path)
                result = _try_write_write(target_path, content or "", "w")
                if result is None:
                    return f"【文件写入成功】{target_path}"
                if isinstance(result, tuple) and result[0] == "fallback":
                    label = "【文件写入成功（回退 _echo）】"
                    if "_echo_workspace" in result[1]:
                        label = "【文件写入成功（回退 _echo_workspace）】"
                    return f"{label}{result[1]}"
                return f"【权限不足】{result[1]}"
            if action == "append":
                parent = os.path.dirname(target_path)
                if parent and not os.path.isdir(parent):
                    os.makedirs(parent, exist_ok=True)
                self._ensure_writable(target_path)
                result = _try_write_write(target_path, content or "", "a")
                if result is None:
                    return f"【文件追加成功】{target_path}"
                if isinstance(result, tuple) and result[0] == "fallback":
                    label = "【文件追加成功（回退 _echo）】"
                    if "_echo_workspace" in result[1]:
                        label = "【文件追加成功（回退 _echo_workspace）】"
                    return f"{label}{result[1]}"
                return f"【权限不足】{result[1]}"
            if action == "create":
                parent = os.path.dirname(target_path)
                if parent and not os.path.isdir(parent):
                    os.makedirs(parent, exist_ok=True)
                if os.path.exists(target_path):
                    return f"【文件已存在】{target_path}"
                self._ensure_writable(target_path)
                result = _try_write_write(target_path, "", "w")
                if result is None:
                    return f"【文件创建成功】{target_path}"
                if isinstance(result, tuple) and result[0] == "fallback":
                    label = "【文件创建成功（回退 _echo）】"
                    if "_echo_workspace" in result[1]:
                        label = "【文件创建成功（回退 _echo_workspace）】"
                    return f"{label}{result[1]}"
                return f"【权限不足】{result[1]}"
            return f"【错误】不支持的操作类型：{action}。请使用 read/write/append/create。"
        except PermissionError as e:
            return f"【权限不足】{str(e)}"
        except Exception as e:
            return f"【文件操作失败】错误信息：{str(e)}"
