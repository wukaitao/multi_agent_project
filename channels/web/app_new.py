"""
Streamlit Web 应用
提供 Agent 的 Web 界面
"""

import streamlit as st
import asyncio
from typing import Dict, Any, Optional
import json
from datetime import datetime

from graphs.main_graph_new import MainGraph
from agents.supervisor.supervisor_agent_new import SupervisorAgent
from config.settings import *

# 页面配置
st.set_page_config(
    page_title="AI Agent 管理平台",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS
st.markdown("""
<style>
    .stApp {
        background-color: #f5f5f5;
    }
    .chat-message-user {
        background-color: #e3f2fd;
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #1976d2;
    }
    .chat-message-agent {
        background-color: #f3e5f5;
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #7b1fa2;
    }
    .chat-message-system {
        background-color: #fff3e0;
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 4px solid #e65100;
    }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .sidebar-section {
        margin-bottom: 20px;
        padding: 15px;
        background-color: #fafafa;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

def create_streamlit_app():
    """创建 Streamlit 应用"""

    # 初始化会话状态
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "agent" not in st.session_state:
        st.session_state.agent = None

    if "current_agent" not in st.session_state:
        st.session_state.current_agent = "supervisor"

    # 初始化 Agent
    if st.session_state.agent is None:
        with st.spinner("正在初始化 Agent..."):
            st.session_state.agent = SupervisorAgent()

    # 侧边栏
    with st.sidebar:
        st.title("AI Agent")
        st.markdown("---")

        # 系统状态
        st.subheader("系统状态")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("状态", "运行中")
        with col2:
            st.metric("消息数", len(st.session_state.messages))

        # Agent 选择
        st.markdown("---")
        st.subheader("Agent 选择")
        agent_options = {
            "supervisor": "监督者 Agent",
            "chat": "对话 Agent",
            "rag": "RAG Agent",
            "medical": "医疗 Agent",
            "finance": "金融 Agent",
            "coding": "编程 Agent",
            "office": "办公 Agent"
        }
        selected_agent = st.selectbox(
            "选择 Agent",
            options=list(agent_options.keys()),
            format_func=lambda x: agent_options.get(x, x),
            index=0
        )
        if selected_agent != st.session_state.current_agent:
            st.session_state.current = selected_agent
            st.rerun()

        # 领域选择
        st.markdown("---")
        st.subheader("领域过滤")
        domain = st.selectbox(
            "领域",
            ["自动检测", "医疗", "金融", "编程", "办公", "娱乐"],
            index=0
        )

        # 高级配置
        st.markdown("---")
        with st.exception("高级配置"):
            max_iterations = st.slider("最大迭代次数", 1, 20, 10)
            temperature = st.slider("温度", 0.0, 1.0, 0.7, 0.1)
            enable_streaming = st.checkbox("启用流式输出", value=True)

            if st.button("重置会话"):
                st.session_state.messages = []
                st.rerun()
            
            if st.button("清空缓存"):
                st.cache_data.clear()
                st.success("缓存已清空")

        # 统计信息
        st.markdown("---")
        st.subheader("统计信息")
        stats = st.session_state.agent.get_stats() if st.session_state.agent else {}
        col1, col2 = st.columns(2)
        with col1:
            st.metric("总请求", stats.get("total_requests", 0))
        with col2:
            st.metric("平均响应", f"{stats.get('avg_response_time', 0):.2f}s")

        st.caption(f"v1.0.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 主区域
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header(f"{agent_options.get(st.session_state.current_agent, '对话')}")

        # 显示聊天历史
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(
                        f'<div class="chat-message-user">'
                        f'<strong>你</strong><br>{msg["content"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                elif msg["role"] == "agent":
                    st.markdown(
                        f'<div class="chat-message-agent">'
                        f'<strong>Agent</strong><br>{msg["content"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                elif msg["role"] == "system":
                    st.markdown(
                        f'<div class="chat-message-system">'
                        f'<strong>系统</strong><br>{msg["content"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        
        # 输入区域
        with st.container():
            col_input, col_button = st.columns([4, 1])
            with col_input:
                user_input = st.text_input(
                    "输入消息...",
                    placeholder="请输入你的问题...",
                    key="user_input",
                    label_visibility="collapsed"
                )
            with col_button:
                send_button = st.button("发送", type="primary", use_container_width=True)

        # 处理消息
        if send_button and user_input:
            # 添加用户消息
            st.session_state.messages.append({
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            })

            # 处理消息
            with st.spinner("正在思考..."):
                try:
                    # 调试 Agent
                    response = asyncio.run(
                        st.session_state.agent.process({
                            "query": user_input,
                            "user_id": "web_user",
                            "domain": None if domain == "自动检测" else domain.lower()
                        })
                    )

                    # 添加 Agent 响应
                    anwser = response.get("answer", "抱歉, 我没有理解你的问题.")
                    st.session_state.messages.append({
                        "role": "agent",
                        "content": anwser,
                        "timestamp": datetime.now().isoformat()
                    })

                except Exception as e:
                    st.session_state.messages.append({
                        "role": "system",
                        "content": f"处理失败: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })

            st.rerun()

        # 右侧面板
        with col2:
            st.subheader("详细信息")

            # 当前状态
            with st.container():
                st.markdown('<div class="sidebar-section>"', unsafe_allow_html=True)
                st.markdown('**当前会话**')
                st.caption(f"消息数: {len(st.session_state.messages)}")
                st.caption(f"Agent: {agent_options.get(st.session_state.current_agent, '未知')}")
                st.caption(f"领域: {domain}")
                st.markdown('</div>', unsafe_allow_html=True)

            # 最近消息预览
            with st.container():
                st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
                st.markdown("**最新消息**")
                if st.session_state.messages:
                    last_msg = st.session_state.messages[-1]
                    st.caption(f"{last_msg['role']}: {last_msg['content'][:100]}...")
                else:
                    st.caption("暂无消息")
                st.markdown('</div>', unsafe_allow_html=True)

            # 快速操作
            with st.container():
                st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
                st.markdown("**快速操作**")

                quick_queries = [
                    "帮我分析这个症状",
                    "查询今天的股票行情",
                    "写一个 Python 函数排序列表",
                    "安排明天下午的会议"
                ]

                for query in quick_queries:
                    if st.button(f"{query}", key=f"quick_{query[:10]}"):
                        st.session_state.user_input = query
                        # 触发发送
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

            # 系统监控
            with st.container():
                st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
                st.markdown("**系统监控**")

                # 模拟数据
                st.progress(0.75, text="CPU使用率: 75%")
                st.progress(0.45, text="内存使用率: 45%")
                st.progress(0.30, text="GPU使用率: 30%")

                st.caption(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")
                st.markdown('</div>', unsafe_allow_html=True)

def main():
    """主入口"""
    create_streamlit_app()

if __name__ == "__main__":
    main()