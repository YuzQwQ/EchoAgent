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

    def analyze_image(self, image_data: bytes, mime_type: str = "image/jpeg", mode: str = "chat", game_context: Optional[dict] = None, previous_context: Optional[str] = None) -> str:
        """
        调用视觉模型分析图片
        
        Args:
            image_data: 图片的二进制数据
            mime_type: 图片 MIME 类型
            mode: "chat" (用户主动询问) 或 "observer" (观察模式)
            game_context: 游戏上下文信息，例如 {"name": "泰拉瑞亚", "keywords": ["血条", "Boss", "道具"]}
            previous_context: 上一帧的视觉描述，用于差异分析 (热启动)
            
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
                # 游戏模式下的观察 Prompt
                if game_context:
                    game_name = game_context.get("name", "Unknown Game")
                    
                    # 泰拉瑞亚专用逻辑
                    if game_name == "Terraria" or game_name == "泰拉瑞亚":
                        system_instruction = f"""
                        你是 Echo 的视觉神经，现在用户正在玩《泰拉瑞亚》(Terraria)。
                        你的任务是分析当前游戏状态，并与上一帧（如果提供）进行对比，判断局势。
                        
                        请关注以下 UI 元素：
                        1. **生命值 (HP)**: 右上角的红心/金心。判断是否危急（红血）。
                        2. **Boss 血条**: 屏幕底部是否有巨大的 Boss 血条（如肉山 Wall of Flesh, 机械骷髅王 Skeletron Prime）。
                        3. **聊天栏**: 左下角的绿色/紫色文字，寻找死亡信息 ("Player was slain by...") 或事件信息 ("The Blood Moon is rising...")。
                        4. **状态栏**: 左上角的 Buff/Debuff 图标。
                        
                        上一帧状态: {previous_context if previous_context else "无 (这是第一帧)"}
                        
                        请返回 JSON 格式结果（不要包含 Markdown 代码块）：
                        {{
                            "description": "简要描述当前画面（如：正在地狱打肉山，血量剩余 20%）。如果有 Boss，必须写出 Boss 名字。",
                            "status": {{
                                "hp_status": "healthy | damaged | critical | dead",
                                "boss_active": "None | [Boss Name]",
                                "event_active": "None | [Event Name]"
                            }},
                            "diff_analysis": "与上一帧相比的关键变化（如：血量骤降、Boss 出现、玩家死亡）。",
                            "category": "IGNORE | NOTICE | SOFTSPEAK | SPEAK"
                        }}
                        
                        【Category 判定标准】
                        - SPEAK: 玩家死亡、Boss 出现、Boss 被击败、血量极度危急(critical)、稀有事件发生。
                        - SOFTSPEAK: 血量下降(damaged)、进入新生物群系、拾取重要物品。
                        - IGNORE/NOTICE: 正常跑图、挖掘、建造、挂机。
                        """
                        prompt_text = f"分析《泰拉瑞亚》截图。上一帧: {previous_context[:100] if previous_context else 'None'}..."
                    else:
                        # 通用游戏逻辑 (保留原样或微调)
                        system_instruction = f"""
                        你是 Echo 的视觉神经，现在用户正在玩游戏《{game_name}》。
                        请分析用户屏幕截图，并返回 JSON 格式结果（不要包含 Markdown 代码块）：
                        {{
                            "description": "简要描述画面（战斗/跑图/剧情/菜单），必须包含看到的关键文字（如Boss名、任务目标）",
                            "ocr_keywords": ["识别到的文字1", "识别到的文字2"],
                            "category": "IGNORE | NOTICE | SOFTSPEAK | SPEAK"
                        }}
                        
                        【Category 游戏模式特化】
                        1. IGNORE: 静态加载图、无意义跑图。
                        2. NOTICE: 正常战斗、整理背包。
                        3. SOFTSPEAK: 遇到新敌人、进入新地图、血量健康但战斗胶着。
                        4. SPEAK: 
                           - 角色死亡/Game Over (重点检测)。
                           - 击败 BOSS (Victory)。
                           - 遇到著名场景或 NPC。
                           - 血量危急 (红血)。
                        
                        严禁：不要给建议。不要输出 JSON 以外的内容。
                        """
                        prompt_text = f"分析《{game_name}》的游戏截图，提取 UI 文字和状态。"
                else:
                    # 原有普通观察 Prompt
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
