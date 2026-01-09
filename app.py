import streamlit as st
import time
from core.agent import EchoAgent
from config import config

# 设置页面标题和图标
st.set_page_config(page_title=config.APP_TITLE, page_icon="🤖")

def main():
    st.title(config.APP_TITLE)

    # 初始化 Agent
    if "agent" not in st.session_state:
        st.session_state.agent = EchoAgent()

    # 侧边栏：功能区
    with st.sidebar:
        st.header("功能区")
        if st.button("🗑️ 清空对话记忆"):
            st.session_state.agent.clear_memory()
            st.rerun()
        
        st.markdown("---")
        
        # --- 视觉输入区域 ---
        st.header("👁️ 视觉输入")
        # key 用于手动重置 uploader
        if "uploader_key" not in st.session_state:
            st.session_state.uploader_key = 0
            
        uploaded_file = st.file_uploader(
            "上传图片给 Echo", 
            type=["png", "jpg", "jpeg"],
            key=f"uploader_{st.session_state.uploader_key}"
        )
        
        if uploaded_file is not None:
            st.image(uploaded_file, caption="预览", use_container_width=True)
            if st.button("📤 发送图片"):
                # 处理图片
                with st.chat_message("assistant", avatar=config.ECHO_AVATAR):
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    # 读取数据
                    bytes_data = uploaded_file.getvalue()
                    mime_type = uploaded_file.type
                    
                    for chunk in st.session_state.agent.process_image(bytes_data, mime_type):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                
                # 重置 Uploader
                st.session_state.uploader_key += 1
                st.rerun()

        st.markdown("---")
        st.markdown(f"**Chat Model:** `{config.PRIMARY_MODEL_NAME}`")
        st.markdown(f"**Vision Model:** `{config.VISION_MODEL_NAME}`")

    # 显示对话历史
    history = st.session_state.agent.get_history()
    for msg in history:
        role = msg["role"]
        content = msg["content"]
        # 视觉观察消息特殊处理：不显示 System Prompt 的原始文本，而是显示更友好的提示
        if role == "user" and content.startswith("【视觉观察】"):
             with st.chat_message("user", avatar=config.USER_AVATAR):
                 st.info(f"🖼️ [发送了一张图片]\n\n{content.split('内容描述]: ')[-1]}")
        # 普通消息
        elif role != "system":
            avatar = config.USER_AVATAR if role == "user" else config.ECHO_AVATAR
            with st.chat_message(role, avatar=avatar):
                st.markdown(content)

    # 处理用户输入
    if prompt := st.chat_input("输入你想说的话..."):
        # 1. 显示用户输入
        with st.chat_message("user", avatar=config.USER_AVATAR):
            st.markdown(prompt)

        # 2. 显示 Echo 回应 (流式)
        with st.chat_message("assistant", avatar=config.ECHO_AVATAR):
            message_placeholder = st.empty()
            full_response = ""
            for chunk in st.session_state.agent.chat(prompt):
                full_response += chunk
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
if __name__ == "__main__":
    main()
