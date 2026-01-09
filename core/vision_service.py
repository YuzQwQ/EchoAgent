from openai import OpenAI
from config import config
import base64
from typing import Optional

class VisionService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.VISION_API_KEY,
            base_url=config.VISION_BASE_URL
        )
        self.model = config.VISION_MODEL_NAME

    def analyze_image(self, image_data: bytes, mime_type: str = "image/jpeg") -> str:
        """
        调用视觉模型分析图片
        
        Args:
            image_data: 图片的二进制数据
            mime_type: 图片 MIME 类型 (image/jpeg, image/png)
            
        Returns:
            图片的文本描述
        """
        if not config.VISION_API_KEY:
            return "⚠️ 视觉模型 API Key 未配置"

        try:
            # 转为 Base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # 构造 Prompt
            # 我们希望 Vision Model 扮演一个客观的观察者，提取所有细节
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "请仔细观察这张图片。1. 如果包含文字，请进行 OCR 识别并输出文字内容。2. 描述图片中的主要物品、场景或人物。3. 如果有显著的细节（如颜色、数量、状态），也请列出。请直接输出描述，不要加开场白。"
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
                max_tokens=500  # 限制描述长度，避免废话太多
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"图片识别失败: {str(e)}"
