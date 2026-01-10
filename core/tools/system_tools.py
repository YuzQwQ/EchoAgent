from core.tools.base import BaseTool
from config import config
import os

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
        description = (
            "系统自省工具。用于查询当前运行环境、版本和开发者配置。"
            "当前运行环境：Electron Desktop App (Windows)。"
            "架构模式：Client-Server (FastAPI + React/HTML)。"
        )
        super().__init__("SystemSelfAwareness", description)

    def execute(self, **kwargs):
        return "System Online."
