from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from core.agent import EchoAgent
from core.tts_service import TTSService
from config import config
import uvicorn
import asyncio
import json
import base64
import re
import speech_recognition as sr
import io

app = FastAPI(title="Echo API Service")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Agent 和 TTS
agent = EchoAgent()
tts_service = TTSService()

def sanitize_text_for_tts(text: str) -> str:
    """
    清洗文本，去除不适合 TTS 朗读的符号（如 Emoji、Markdown、动作描写、情感标签）
    """
    # 0. [新增] 去除情感标签 [emotion:xxx] 和其他可能的标签
    # 匹配 [key:value] 格式，更宽泛地匹配 value 部分，防止特殊字符漏网
    text = re.sub(r'\[\w+:[^\]]+\]', '', text)
    
    # 1. 去除 Emoji (简单范围匹配)
    # 这是一个比较宽泛的 regex，匹配常见 emoji 和图形符号
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    
    # 2. 去除 Markdown 粗体/斜体符号 (*, **)
    text = text.replace("**", "").replace("*", "")
    
    # 3. 去除括号内的动作描写 (e.g., （笑）, (叹气))
    # 匹配中文全角括号和英文半角括号
    text = re.sub(r'（.*?）', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    
    # 4. 替换换行符为逗号或句号，增加自然停顿
    text = text.replace("\n", "，")
    
    # 5. 去除多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_input = message_data.get("content", "")
            msg_type = message_data.get("type", "text") # text, image, audio
            enable_tts = message_data.get("enable_tts", False) # 接收前端开关状态

            # 处理语音消息 (STT)
            if msg_type == "audio":
                try:
                    # 1. 解码 Base64
                    audio_data_str = user_input
                    if "base64," in audio_data_str:
                        _, encoded = audio_data_str.split("base64,", 1)
                        audio_bytes = base64.b64decode(encoded)
                    else:
                        audio_bytes = base64.b64decode(audio_data_str)
                    
                    # 2. 使用 SpeechRecognition 处理
                    r = sr.Recognizer()
                    # 这里的 BytesIO 必须包含完整的 WAV 文件数据（含头信息）
                    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                        audio = r.record(source)
                    
                    # 3. 调用 Google STT (需联网)
                    print("Recognizing speech...")
                    # show_all=False 返回最佳结果字符串
                    # 使用 run_in_executor 避免阻塞事件循环
                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(None, lambda: r.recognize_google(audio, language="zh-CN"))
                    print(f"Recognized text: {text}")
                    
                    if text:
                        user_input = text
                        msg_type = "text" # 转为文本处理流程
                        
                        # 告诉前端识别结果，用于显示用户消息
                        await websocket.send_json({
                            "type": "user_input", 
                            "content": text
                        })
                    else:
                        await websocket.send_json({"type": "error", "content": "未能识别出语音"})
                        continue
                        
                except sr.UnknownValueError:
                    print("STT: UnknownValueError")
                    await websocket.send_json({"type": "error", "content": "听不清，请再说一遍"})
                    continue
                except sr.RequestError as e:
                    print(f"STT: RequestError {e}")
                    await websocket.send_json({"type": "error", "content": "语音服务连接失败，请检查网络"})
                    continue
                except Exception as e:
                    print(f"STT Error: {e}")
                    await websocket.send_json({"type": "error", "content": f"语音处理错误: {str(e)}"})
                    continue

            if not user_input and msg_type == "text":
                continue

            # 处理图片
            if msg_type == "image":
                 try:
                     # 前端传来的 content 应该是 base64 字符串
                     image_data_str = message_data.get("content", "")
                     mime_type = "image/jpeg" # 默认
                     
                     if "base64," in image_data_str:
                         header, encoded = image_data_str.split("base64,", 1)
                         # 尝试从 header 提取 mime type
                         if "data:" in header and ";" in header:
                             mime_type = header.split("data:")[1].split(";")[0]
                         image_bytes = base64.b64decode(encoded)
                     else:
                         image_bytes = base64.b64decode(image_data_str)
                     
                     # 调用 agent 处理
                     full_response = ""
                     for chunk in agent.process_image(image_bytes, mime_type):
                        full_response += chunk
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                            "is_final": False
                        })
                        await asyncio.sleep(0.01)
                        
                     # 结束标记
                     await websocket.send_json({
                        "type": "done",
                        "content": "",
                        "is_final": True
                     })
                     
                 except Exception as e:
                    error_msg = f"Image Error: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "content": error_msg
                    })

            # 处理文本对话
            elif msg_type == "text":
                # 流式回复 + TTS 分句缓冲
                full_response = ""
                tts_buffer = ""
                
                # 优化分句正则：更严格的切分，支持换行作为切分点
                # 排除省略号(...)以免切碎句子
                sentence_endings = re.compile(r'(?<!\.)[.!?。？！\n]+')

                try:
                    for chunk in agent.chat(user_input):
                        full_response += chunk
                        tts_buffer += chunk
                        
                        # 发送文本块给前端
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                            "is_final": False
                        })

                        # TTS 处理逻辑
                        if enable_tts:
                            # 检查是否有句子结束符
                            match = sentence_endings.search(tts_buffer)
                            if match:
                                # 找到结束符，切分句子
                                end_pos = match.end()
                                raw_sentence = tts_buffer[:end_pos].strip()
                                tts_buffer = tts_buffer[end_pos:] # 剩余部分留给下一次
                                
                                # 清洗文本（去 Emoji，去动作描写）
                                clean_sentence = sanitize_text_for_tts(raw_sentence)
                                
                                if clean_sentence:
                                    # 生成语音
                                    audio_base64 = await tts_service.text_to_speech(clean_sentence)
                                    
                                    if audio_base64:
                                        await websocket.send_json({
                                            "type": "audio",
                                            "content": audio_base64
                                        })

                        await asyncio.sleep(0.01)
                    
                    # 循环结束后，处理剩余的 buffer
                    if enable_tts and tts_buffer.strip():
                        raw_sentence = tts_buffer.strip()
                        clean_sentence = sanitize_text_for_tts(raw_sentence)
                        
                        if clean_sentence:
                            audio_base64 = await tts_service.text_to_speech(clean_sentence)
                            if audio_base64:
                                await websocket.send_json({
                                    "type": "audio",
                                    "content": audio_base64
                                })

                    # 发送结束标记
                    await websocket.send_json({
                        "type": "done",
                        "content": "",
                        "is_final": True
                    })
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    print(error_msg)
                    await websocket.send_json({
                        "type": "error",
                        "content": error_msg
                    })
                    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok", "model": config.PRIMARY_MODEL_NAME}

if __name__ == "__main__":
    # 开发模式下运行
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
