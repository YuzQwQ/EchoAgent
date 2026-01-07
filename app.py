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
        st.markdown(f"**Model:** `{config.LLM_MODEL}`")
        st.markdown(f"**History File:** `{config.HISTORY_FILE}`")

    # 显示对话历史
    history = st.session_state.agent.get_history()
    for msg in history:
        role = msg["role"]
        content = msg["content"]
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
        
        # 3. 主动发言逻辑 (已暂时移除)
        # 待未来优化“情绪泄露”逻辑后再上线

        
        # 强制刷新以更新历史记录显示（虽然上面已经显示了，但为了保持一致性）
        # 也可以不刷新，依靠下一次交互
        # st.rerun() 

if __name__ == "__main__":
    main()
