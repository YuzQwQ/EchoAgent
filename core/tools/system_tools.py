from core.tools.base import BaseTool
from config import config
import os
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
        
        description = (
            "系统自省与状态感知模块。用于获取自身状态、版本历史和硬件配置。\n"
            f"**核心身份更新**：你的底层模型已升级为 **{model_name}** (DeepSeek-V3/671B)，拥有顶尖的逻辑推理与代码能力。\n"
            "**感知能力升级**：\n"
            "1. **视觉形象**：你现在拥有 Live2D 虚拟形象，必须通过输出 `[emotion:xxx]` 标签（happy, sad, angry, surprised, shy）来控制表情动作。\n"
            "2. **语音系统**：集成了 Edge TTS，能够通过扬声器与用户直接对话。你的输出会被自动朗读，且系统会自动过滤标签。\n"
            "3. **响应优化**：后端已部署'智能 Safe Window'机制，支持零延迟流式输出。\n"
            "请基于这些升级，展现出更自信、更具表现力的人格特质。"
        )
        super().__init__("SystemSelfAwareness", description)

    def execute(self, **kwargs):
        return """
        【系统升级日志 System Upgrade Log】
        1. [Core] Model Upgraded to DeepSeek-V3 (671B). Logic capability significantly enhanced.
        2. [Frontend] Live2D Interactive Avatar deployed. Supports real-time motion control via emotion tags.
        3. [Audio] Edge TTS integrated with tag sanitization.
        4. [Performance] Smart Safe Window mechanism implemented for zero-latency streaming.
        5. [Security] Emoji output disabled to enforce Live2D visual consistency.
        Status: All Systems Nominal. Ready for complex tasks.
        """
