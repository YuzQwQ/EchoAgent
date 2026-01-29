from openai import OpenAI
from config import config
import base64
from typing import Optional

class VisionService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.VISION_MODEL_API_KEY,
            base_url=config.VISION_MODEL_BASE_URL
        )
        self.model = config.VISION_MODEL

    def analyze_image(self, image_data: bytes, mime_type: str = "image/jpeg", mode: str = "chat") -> str:
        """
        调用视觉模型分析图片
        
        Args:
            image_data: 图片的二进制数据
            mime_type: 图片 MIME 类型
            mode: "chat" (用户主动询问) 或 "observer" (观察模式)
            
        Returns:
            图片的文本描述 (JSON 字符串 或 普通文本)
        """
        if not config.VISION_MODEL_API_KEY:
            return "⚠️ 视觉模型 API Key 未配置"

        try:
            # 转为 Base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # 构造 Prompt
            if mode == "observer":
                system_instruction = """
                你是 Echo 的视觉神经。请分析用户屏幕截图，并返回 JSON 格式结果（不要包含 Markdown 代码块）：
                {
                    "description": "一句话客观描述当前画面（如：用户正在 VSCode 中编写 Python 代码）",
                    "category": "IGNORE | NOTICE | SOFTSPEAK | SPEAK"
                }
                
                【Category 定义决策树】
                1. IGNORE (Level 0):
                   - 静态桌面、文档、发呆、无明显变化的网页。
                   - 没有任何值得注意的信息。

                2. NOTICE (Level 1):
                   - 琐碎的操作（如文件管理、简单的窗口切换、系统设置）。
                   - 正常的网页浏览（无明显情绪点）。
                   - 即使是视频/游戏，如果画面平淡无奇，也归为此类。
                   
                3. SOFTSPEAK (Level 1.5):
                   - 【条件】: 用户正在进行持续性的具体活动，且画面内容**有一定趣味但不够炸裂**。
                   - 例子：正在写代码（且代码屏占满）、正在看B站普通视频、正在逛淘宝、正在玩游戏（平淡期）。
                   - 意图：轻轻哼一声，表示“我在陪你”。

                4. SPEAK (Level 2):
                   - 【条件】: 极具戏剧性、反差强烈、或极其重要的时刻。
                   - 例子：游戏胜利/失败结算画面（Game Over/Victory）、软件红一片报错、购买了昂贵商品、长时间刷视频突然切回工作（反差）。
                   - 意图：必须大声吐槽。

                严禁：不要输出 OCR 细节。不要给建议。不要输出 JSON 以外的内容。
                """
                prompt_text = "请分析这张屏幕截图，按要求输出 JSON。"
            else:
                # 原有的聊天模式 Prompt
                system_instruction = "你是一个客观的观察者，请描述图片细节。"
                prompt_text = "请仔细观察这张图片。1. 如果包含文字，请进行 OCR 识别。2. 描述主要物品、场景或人物。请直接输出描述。"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": system_instruction
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": prompt_text
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                # 尝试强制 JSON 输出 (部分模型支持)
                response_format={"type": "json_object"} if mode == "observer" else None
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"图片识别失败: {str(e)}"
