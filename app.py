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
        
        # 3. 尝试主动发言逻辑
        # 我们使用一个简单的 sleep 模拟“思考”间隔，然后检查是否要主动发言
        # 注意：这会阻塞 UI 一小会儿，但在聊天场景中是可以接受的，模拟“对方正在输入...”
        
        with st.status("Echo 正在思考...", expanded=False) as status:
            time.sleep(2) # 假装思考/等待
            
            proactive_response = ""
            proactive_generator = st.session_state.agent.proactive_chat()
            
            # 如果生成器不为空（即有主动发言）
            if proactive_generator:
                status.update(label="Echo 想要补充...", state="running")
                # 预先创建一个空的 chat message 容器
                # 但由于我们还在 if prompt 块里，这里的 container 可能位置不对
                # 最好是先把 generator 跑完拿到结果，如果非空，再渲染
                
                # 这里我们稍微 hack 一下，直接在当前循环里渲染，或者存入 session state 触发 rerun
                # 为了简单直接，我们直接渲染
                
                # 创建一个新的 placeholder 用于显示主动发言
                # 注意：我们需要跳出上面的 with chat_message 块
                
                # 收集主动发言内容
                for chunk in proactive_generator:
                    proactive_response += chunk
            
            status.update(label="思考完毕", state="complete", expanded=False)

        # 如果有主动发言，显示出来
        if proactive_response:
             with st.chat_message("assistant", avatar=config.ECHO_AVATAR):
                st.markdown(proactive_response)
        
        # 强制刷新以更新历史记录显示（虽然上面已经显示了，但为了保持一致性）
        # 也可以不刷新，依靠下一次交互
        # st.rerun() 

if __name__ == "__main__":
    main()
