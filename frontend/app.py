# frontend/app.py
import sys
import os
import yaml
import streamlit as st
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
from dotenv import load_dotenv

# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 导入视图
from frontend.views import chat, deep_read, deep_qa, kb_management, deep_write_v2
from src.db import init_db

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Pro", layout="wide", page_icon="🕵️‍♂️")

# 初始化数据库
init_db()

# === 全局 CSS 样式 ===
st.markdown("""
<style>
    .stApp { font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    .stDeployButton {display: none;}
    /* 引用 tooltip 样式 */
    .ref-container { position: relative; display: inline-block; color: #1f77b4; cursor: help; border-bottom: 1px dashed #1f77b4; }
    .ref-container .ref-tooltip { visibility: hidden; width: 320px; background-color: #fff; border: 1px solid #e0e0e0; padding: 12px; border-radius: 8px; position: absolute; bottom: 120%; left: 50%; transform: translateX(-50%); opacity: 0; transition: opacity 0.2s; z-index: 999; box-shadow: 0 4px 20px rgba(0,0,0,0.15); font-size: 14px; font-weight: normal; color: #333; pointer-events: none; }
    .ref-container:hover .ref-tooltip { visibility: visible; opacity: 1; }
    /* 侧边栏按钮 */
    section[data-testid="stSidebar"] button { border: none !important; text-align: left !important; padding-left: 10px !important; }
</style>
""", unsafe_allow_html=True)

# === Session 初始化 ===
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
# 添加 next_query 的初始化
if "next_query" not in st.session_state:
    st.session_state.next_query = ""

def main():
    try:
        with open('config.yaml') as file:
            config = yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("⚠️ 找不到 config.yaml")
        return
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config.get('preauthorized')
    )
    
    authenticator.login()
    
    if st.session_state["authentication_status"]:
        authenticator.logout(location='sidebar')
        with st.sidebar:
            st.title("DeepSeek RAG")
            # 这里的顺序对应下面的 if-else
            page = st.radio(
                "导航",
                ["💬 对话", "🧠 深度解读", "❓ 深度追问", "📰 新闻工作室 (New)", "⚙️ 知识库"],
                index=3,
            )

        if page == "💬 对话":
            chat.render()
        elif page == "🧠 深度解读":
            deep_read.render()
        elif page == "❓ 深度追问":
            deep_qa.render()
        elif page == "📰 新闻工作室 (New)":
            deep_write_v2.render()
        else:
            kb_management.render()
            
    elif st.session_state["authentication_status"] is False:
        st.error('用户名或密码不正确')
    elif st.session_state["authentication_status"] is None:
        st.warning('请输入用户名和密码')

if __name__ == "__main__":
    main()