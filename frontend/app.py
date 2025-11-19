"""Streamlit 前端入口：支持多知识库管理。"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document

# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents
from src.storage import save_kb, load_kbs, list_kbs, delete_kb

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Pro", layout="wide")

# 初始化 session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_kbs" not in st.session_state:
    st.session_state.selected_kbs = []


def render_kb_management():
    """知识库管理界面。"""
    st.header("📂 知识库管理")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("现有知识库")
        existing_kbs = list_kbs()
        if not existing_kbs:
            st.info("暂无知识库，请在右侧创建。")
        
        for kb in existing_kbs:
            c1, c2 = st.columns([3, 1])
            c1.write(f"📄 {kb}")
            if c2.button("删除", key=f"del_{kb}", type="primary"):
                delete_kb(kb)
                st.success(f"已删除知识库: {kb}")
                st.rerun()

    with col2:
        st.subheader("新建 / 追加知识")
        
        # 1. 选择或输入知识库名称
        kb_action = st.radio("操作模式", ["追加到现有", "新建知识库"], horizontal=True)
        
        target_kb_name = ""
        if kb_action == "追加到现有":
            if existing_kbs:
                target_kb_name = st.selectbox("选择知识库", existing_kbs)
            else:
                st.warning("请先新建知识库")
        else:
            target_kb_name = st.text_input("输入新知识库名称 (英文/数字)", placeholder="example_kb")

        # === 新增：选择知识库语言 ===
        kb_language = st.selectbox(
            "选择文档主要语言 (用于优化检索)",
            ["Chinese", "English", "Japanese", "Korean", "French"],
            index=0,
            help="DeepSeek 会将搜索词自动转换为此语言，提高检索准确率。"
        )
        # ===========================

        # 2. 上传文件或文本
        upload_mode = st.tabs(["📁 上传文件", "📝 粘贴文本"])
        raw_docs = []
        
        with upload_mode[0]:
            uploaded_files = st.file_uploader("上传 PDF/TXT", type=["pdf", "txt"], accept_multiple_files=True)
        
        with upload_mode[1]:
            text_input = st.text_area("输入长文本", height=150)

        # 3. 提交按钮
        if st.button("💾 保存到知识库", use_container_width=True, key="save_kb_btn"):
            if not target_kb_name:
                st.error("知识库名称不能为空！")
                return
                
            with st.spinner("正在处理..."):
                # 处理文件
                if uploaded_files:
                    for f in uploaded_files:
                        raw_docs.extend(load_file(f))
                
                # 处理文本
                if text_input:
                    raw_docs.append(Document(page_content=text_input, metadata={"source": "text_input"}))
                
                if not raw_docs:
                    st.warning("没有检测到输入内容。")
                    return

                # 切分并保存
                chunks = split_documents(raw_docs)
                
                # === 修改：传入 selected language ===
                save_kb(target_kb_name, chunks, language=kb_language)
                # ==================================
                
                st.success(f"成功将 {len(chunks)} 个片段存入知识库: [{target_kb_name}] (语言: {kb_language})")
                st.rerun()


def render_chat():
    """聊天界面及处理逻辑。"""
    
    # --- 侧边栏：在聊天模式下显示知识库选择 ---
    # 注意：Streamlit 会按顺序在 Sidebar 追加内容
    with st.sidebar:
        st.divider()
        st.subheader("🧠 知识库选择")
        all_kbs = list_kbs()
        selected_kbs = st.multiselect(
            "选择要检索的知识库", 
            all_kbs,
            default=all_kbs[0] if all_kbs else None
        )
        
        if not selected_kbs:
            st.warning("⚠️ 请至少选择一个知识库")
        else:
            st.success(f"已加载 {len(selected_kbs)} 个库")
            
        st.session_state.selected_kbs = selected_kbs

    # --- 主区域：聊天历史 ---
    st.header("💬 智能问答")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --- 底部：聊天输入框 ---
    # 这里 st.chat_input 是在主层级调用的，没有嵌套在 Tabs 里，因此不会报错
    user_input = st.chat_input("请输入问题...", key="chat_input")
    
    if user_input:
        selected_kbs = st.session_state.get("selected_kbs", [])
        
        if not selected_kbs:
            st.error("请先在左侧侧边栏选择知识库！")
            return

        # 1. 加载选中的知识库文档到内存
        with st.spinner("正在加载知识库索引..."):
            source_documents = load_kbs(selected_kbs)

        # 2. 显示用户输入
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 3. 构造输入并调用 Agent
        inputs = {
            "question": user_input,
            "source_documents": source_documents,
            "search_count": 0,
            "search_needed": False
        }

        with st.chat_message("assistant"):
            status_box = st.status("Agent 思考中...", expanded=True)
            final_res = ""
            
            try:
                for output in graph.stream(inputs):
                    for key, val in output.items():
                        if key == "retrieve":
                            docs = val.get("retrieved_documents", [])
                            n = len(docs)
                            status_box.write(f"🔍 在选定库中检索到 {n} 条线索")
                            
                            # 遍历显示检索到的具体内容
                            for i, doc in enumerate(docs):
                                status_box.markdown(f"**📄 线索 {i + 1}**")
                                # 使用引用格式 (>) 显示文本内容，使其在 UI 上有区分度
                                status_box.markdown(f"> {doc.page_content}")
                                # 显示元数据（例如文件名）
                                source = doc.metadata.get("source", "未知来源")
                                status_box.caption(f"来源: {source}")
                                status_box.markdown("---") # 添加分割线
                        elif key == "transform_query":
                            q = val.get("question")
                            status_box.write(f"🔄 优化搜索词: {q}")
                        elif key == "generate":
                            final_res = val.get("generation")
                
                # 运行结束后，状态改为完成
                # expanded=False 会默认折叠，用户点击 "回答完成" 即可再次展开查看刚才的线索
                status_box.update(label="回答完成 (点击查看思考过程)", state="complete", expanded=False)
                
                if final_res:
                    st.markdown(final_res)
                    st.session_state.messages.append({"role": "assistant", "content": final_res})
                else:
                    st.warning("未能生成回答，请检查日志。")

            except Exception as e:
                status_box.update(label="发生错误", state="error")
                st.error(f"运行错误: {e}")


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        st.warning("请配置 .env 文件中的 DEEPSEEK_API_KEY")

    # --- 使用侧边栏进行页面导航 ---
    with st.sidebar:
        st.title("DeepSeek RAG")
        page = st.radio(
            "功能导航", 
            ["💬 对话模式", "⚙️ 知识库管理"], 
            index=0
        )

    # 根据选择渲染不同的页面（函数）
    if page == "💬 对话模式":
        render_chat()
    elif page == "⚙️ 知识库管理":
        render_kb_management()


if __name__ == "__main__":
    main()