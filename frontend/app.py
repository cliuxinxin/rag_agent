"""Streamlit 前端入口：支持多知识库管理。"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents
from src.storage import save_kb, load_kbs, list_kbs, delete_kb, get_kb_details

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Supervisor", layout="wide")

# 初始化 session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_kbs" not in st.session_state:
    st.session_state.selected_kbs = []


def render_kb_management():
    st.header("📂 知识库管理")
    
    # === 这里定义了两个 Tab ===
    tabs = st.tabs(["📚 知识库列表 & 检视", "➕ 新建/追加知识"])
    
    # === Tab 1: 列表与检视 (你之前没看到的可能是这个) ===
    with tabs[0]:
        existing_kbs = list_kbs()
        if not existing_kbs:
            st.info("暂无知识库。请去第二个标签页新建。")
        else:
            col_list, col_detail = st.columns([1, 2])
            with col_list:
                st.subheader("知识库列表")
                selected_kb_to_view = st.radio("选择知识库查看详情", existing_kbs)
                
                st.markdown("---")
                if st.button(f"🗑️ 删除 {selected_kb_to_view}", type="primary"):
                    delete_kb(selected_kb_to_view)
                    st.success(f"已删除 {selected_kb_to_view}")
                    st.rerun()
            
            with col_detail:
                st.subheader(f"🔍 检视: {selected_kb_to_view}")
                details = get_kb_details(selected_kb_to_view)
                
                m1, m2 = st.columns(2)
                m1.metric("片段数量", details["doc_count"])
                m2.metric("总字符数", details["total_chars"])
                
                st.divider()
                st.write("📄 **内容预览 (随机前5条)**")
                if details["preview"]:
                    for item in details["preview"]:
                        with st.container(border=True):
                            st.caption(f"来源: {item['source']}")
                            st.text(item['content'])
                else:
                    st.write("该知识库为空或无法读取。")

    # === Tab 2: 新建/追加 ===
    with tabs[1]:
        st.subheader("上传文档")
        kb_action = st.radio("模式", ["追加到现有", "新建知识库"], horizontal=True)
        
        target_kb_name = ""
        if kb_action == "追加到现有":
            if existing_kbs:
                target_kb_name = st.selectbox("选择目标库", existing_kbs)
            else:
                st.warning("请先新建")
        else:
            target_kb_name = st.text_input("新库名称 (英文/数字)", placeholder="kb_v1")

        kb_language = st.selectbox("文档主要语言", ["Chinese", "English"], index=0)

        upload_mode = st.tabs(["📁 上传文件", "📝 粘贴文本"])
        raw_docs = []
        
        with upload_mode[0]:
            uploaded_files = st.file_uploader("支持 PDF/TXT", type=["pdf", "txt"], accept_multiple_files=True)
        
        with upload_mode[1]:
            text_input = st.text_area("输入文本", height=150)

        if st.button("💾 开始处理并保存", use_container_width=True):
            if not target_kb_name:
                st.error("请输入名称")
                return
                
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
            with st.spinner("正在处理..."):
                chunks = split_documents(raw_docs)
                
                # 显示进度条
                progress_bar = st.progress(0, text="准备向量化...")
                
                # === 修改：传入 selected language 和 progress bar ===
                save_kb(target_kb_name, chunks, language=kb_language, progress_bar=progress_bar)
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
            # load_kbs 现在返回两个值
            source_documents, vector_store = load_kbs(selected_kbs)

        # 2. 显示用户输入
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 3. 初始化 Graph 输入
        # 将历史消息转换为 LangChain 格式，以便 Agent 拥有多轮对话记忆
        # 这里简化处理，只传当前问题作为起始，如果需要多轮记忆，需从 session_state.messages 转换
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "source_documents": source_documents,
            "vector_store": vector_store,  # 传入 VectorStore
            "next": "Supervisor", # 默认入口
            "current_search_query": "",
            "final_evidence": [],
            # 初始化计数器
            "loop_count": 0,
            
            # === 新增：初始化为空列表 ===
            "attempted_searches": [],
            "failed_topics": []
        }

        with st.chat_message("assistant"):
            # 创建一个容器用于显示实时的思考过程
            status_container = st.status("Supervisor 正在调度...", expanded=True)
            final_answer = ""

            try:
                # === 核心修改：增加 recursion_limit 配置 ===
                # 默认是 25，我们增加到 50，配合代码里的 MAX_LOOPS=6 逻辑双重保险
                graph_config = {"recursion_limit": 50}
                
                # 运行 Graph
                # stream_mode="updates" 会返回每个节点更新的状态
                for step in graph.stream(initial_state, config=graph_config):
                    for node_name, update in step.items():
                        
                        # --- Supervisor 节点 ---
                        if node_name == "Supervisor":
                            next_node = update.get("next")
                            query = update.get("current_search_query")
                            loop = update.get("loop_count", 0)
                            
                            if next_node == "Searcher":
                                status_container.write(f"🔄 **第 {loop} 轮思考**: 发现缺口，指派搜索 `{query}`")
                            elif next_node == "Answerer":
                                status_container.write("✅ **决策**: 信息充足 (或达到上限)，准备回答。")
                        
                        # --- Searcher 节点 ---
                        elif node_name == "Searcher":
                            # Searcher 返回的是 AIMessage
                            if "messages" in update and update["messages"]:
                                msg = update["messages"][0]
                                if hasattr(msg, 'content'):
                                    content = msg.content
                                    status_container.write(f"🔍 Searcher 搜索结果:")
                                    status_container.markdown(content)
                        
                        # --- Answerer 节点 ---
                        elif node_name == "Answerer":
                            # Answerer 返回的是最终回答
                            if "messages" in update and update["messages"]:
                                msg = update["messages"][0]
                                if hasattr(msg, 'content'):
                                    final_answer = msg.content
                                    status_container.write("✅ Answerer 已生成最终回答")
                                    # 不再在这里显示最终回答，避免重复显示
                                    # status_container.markdown(final_answer)
                        
                        # --- END ---
                        elif node_name == "__end__":
                            status_container.update(label="回答完成", state="complete", expanded=False)
                
                # 显示最终回答 (修复重复显示问题)
                if final_answer:
                    # 只在最终回答不为空且未在流中显示时才显示
                    # 检查是否已经在 status_container 中显示过
                    if final_answer not in [msg.get("content", "") for msg in st.session_state.messages]:
                        st.markdown(final_answer)
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})
                else:
                    st.warning("未能生成回答，请检查日志。")
            
            except Exception as e:
                status_container.update(label="发生错误", state="error")
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