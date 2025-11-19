"""Streamlit 前端入口。"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document

# 将项目根目录加入 Python Path 以便导入 src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents

# 加载环境变量
load_dotenv()

st.set_page_config(page_title="DeepSeek Agentic RAG", layout="wide")

# Session State 初始化
if "processed_docs" not in st.session_state:
    st.session_state.processed_docs = []
if "messages" not in st.session_state:
    st.session_state.messages = []


def sidebar_ui():
    """侧边栏 UI 逻辑。"""
    with st.sidebar:
        st.header("📚 知识库构建")
        
        tab_file, tab_text = st.tabs(["📁 上传文件", "📝 粘贴文本"])
        
        raw_docs = []
        is_processed = False

        with tab_file:
            uploaded_file = st.file_uploader("支持 PDF / TXT", type=["pdf", "txt"])
            if uploaded_file and st.button("处理文件", key="btn_file"):
                with st.spinner("正在解析文件..."):
                    raw_docs = load_file(uploaded_file)
                    is_processed = True

        with tab_text:
            text_input = st.text_area("输入长文本", height=200)
            if text_input and st.button("处理文本", key="btn_text"):
                with st.spinner("正在解析文本..."):
                    raw_docs = [Document(page_content=text_input)]
                    is_processed = True

        if is_processed and raw_docs:
            chunks = split_documents(raw_docs)
            st.session_state.processed_docs = chunks
            st.success(f"成功切分 {len(chunks)} 个片段！")


def chat_ui():
    """聊天主界面逻辑。"""
    st.title("🔎 DeepSeek Agentic RAG")
    st.caption("Engineered with LangGraph & Streamlit")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("输入问题...")

    if user_input:
        if not st.session_state.processed_docs:
            st.error("请先在左侧构建知识库！")
            return

        # 1. 显示用户输入
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. 构造初始状态
        # 注意：我们将整个文档列表传入 State，这在无向量库模式下是必须的
        inputs = {
            "question": user_input,
            "source_documents": st.session_state.processed_docs,
            "search_count": 0,
            "search_needed": False
        }

        # 3. 调用后端 Graph
        with st.chat_message("assistant"):
            status_box = st.status("Agent 运行中...", expanded=True)
            final_res = ""
            
            try:
                for output in graph.stream(inputs):
                    for key, val in output.items():
                        if key == "retrieve":
                            n = len(val.get("retrieved_documents", []))
                            status_box.write(f"🔍 检索: 找到 {n} 个片段")
                        elif key == "transform_query":
                            q = val.get("question")
                            status_box.write(f"🔄 重写: {q}")
                        elif key == "generate":
                            final_res = val.get("generation")
                
                status_box.update(label="完成", state="complete", expanded=False)
                st.markdown(final_res)
                st.session_state.messages.append(
                    {"role": "assistant", "content": final_res}
                )

            except Exception as e:
                st.error(f"运行出错: {e}")


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        st.warning("未检测到 DEEPSEEK_API_KEY，请检查 .env 文件。")
    
    sidebar_ui()
    chat_ui()


if __name__ == "__main__":
    main()