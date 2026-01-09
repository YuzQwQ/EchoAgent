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
            msg_type = message_data.get("type", "text") # text or image
            enable_tts = message_data.get("enable_tts", False) # 接收前端开关状态

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
                sentence_endings = re.compile(r'[.!?。？！\n]+')

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
                                sentence = tts_buffer[:end_pos].strip()
                                tts_buffer = tts_buffer[end_pos:] # 剩余部分留给下一次
                                
                                if sentence:
                                    # 异步生成语音（为了不阻塞文本流，最好用 run_in_executor 或简单的 await）
                                    # 由于 tts_service.text_to_speech 是同步的，这里会阻塞一下
                                    # 考虑到这是本地运行，稍微卡顿一下文本输出问题不大，或者我们可以把 TTS 放到后台任务
                                    # 但为了同步性（说完一句播一句），阻塞其实也可以接受
                                    
                                    # 使用 asyncio.to_thread 避免阻塞事件循环
                                    audio_base64 = await asyncio.to_thread(tts_service.text_to_speech, sentence)
                                    
                                    if audio_base64:
                                        await websocket.send_json({
                                            "type": "audio",
                                            "content": audio_base64
                                        })

                        await asyncio.sleep(0.01)
                    
                    # 循环结束后，处理剩余的 buffer
                    if enable_tts and tts_buffer.strip():
                        audio_base64 = await asyncio.to_thread(tts_service.text_to_speech, tts_buffer.strip())
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
