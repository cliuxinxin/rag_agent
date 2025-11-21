"""Streamlit 前端入口：支持多知识库管理。"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

import re  # 新增正则库
# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents
from src.storage import save_kb, load_kbs, list_kbs, delete_kb, get_kb_details

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Pro", layout="wide")

# === 初始化 Session State ===
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_kbs" not in st.session_state:
    st.session_state.selected_kbs = []
# 新增：用于处理点击建议问题后的自动跳转
if "next_query" not in st.session_state:
    st.session_state.next_query = ""
# 新增：状态初始化确保后端不报错
if "attempted_searches" not in st.session_state:
    st.session_state.attempted_searches = []
if "research_notes" not in st.session_state:
    st.session_state.research_notes = []
if "failed_topics" not in st.session_state:
    st.session_state.failed_topics = []


def render_kb_management():
    """知识库管理界面"""
    st.header("📂 知识库管理")
    
    tabs = st.tabs(["📚 知识库列表 & 检视", "➕ 新建/追加知识"])
    
    # === Tab 1: 列表与检视 ===
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
            if text_input:
                from langchain_core.documents import Document
                raw_docs.append(Document(page_content=text_input, metadata={"source": "text_input"}))
            
            if not raw_docs:
                st.warning("没有内容可保存。")
                return

            # 切分 (使用新的通用化参数 chunk_size=800)
            chunks = split_documents(raw_docs, chunk_size=800)
            st.info(f"已切分为 {len(chunks)} 个片段 (Chunk Size=800)")
            
            progress_bar = st.progress(0, text="初始化向量化...")
            
            try:
                save_kb(target_kb_name, chunks, language=kb_language, progress_bar=progress_bar)
                st.success("✅ 保存成功！请切换到“知识库列表”标签页查看。")
                st.rerun()
            except Exception as e:
                st.error(f"保存失败: {e}")


def format_display_message(content):
    """
    辅助函数：优化消息显示
    将“调查笔记”和“原始片段”折叠到 Expander 中，保持界面整洁。
    """
    # 1. 尝试分离主要回答和参考资料
    # 假设 Answerer 的输出中包含【🕵️‍♂️ 调查笔记】或【📚 原始片段】
    split_markers = ["【🕵️‍♂️ 调查笔记】", "【📚 原始片段】", "【原始知识库片段】"]
    
    found_marker = None
    split_index = -1
    
    for marker in split_markers:
        idx = content.find(marker)
        if idx != -1:
            if split_index == -1 or idx < split_index:
                split_index = idx
                found_marker = marker
    
    if split_index != -1:
        main_text = content[:split_index]
        ref_text = content[split_index:]
        
        st.markdown(main_text)
        with st.expander("📚 查看调查笔记与原始引用 (点击展开)", expanded=False):
            st.markdown(ref_text)
    else:
        st.markdown(content)

    # 2. 解析后续建议并显示为按钮
    # 正则匹配： 1. [点击] 问题内容
    suggestions = re.findall(r"\d+\.\s+\[点击\]\s+(.*)", content)
    if suggestions:
        st.markdown("---")
        st.caption("👉 **您可以点击以下问题继续追问：**")
        # 使用 columns 布局按钮
        cols = st.columns(len(suggestions))
        for idx, question in enumerate(suggestions):
            # 按钮 key 需要唯一
            if cols[idx].button(question, key=f"sugg_{hash(content)}_{idx}"):
                st.session_state.next_query = question
                st.rerun()

def render_chat():
    with st.sidebar:
        st.divider()
        st.subheader("🧠 知识库选择")
        all_kbs = list_kbs()
        selected_kbs = st.multiselect("选择知识库", all_kbs, default=all_kbs[0] if all_kbs else None)
        st.session_state.selected_kbs = selected_kbs

    st.header("💬 DeepSeek Research Agent")

    # 显示历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                format_display_message(msg["content"])
            else:
                st.markdown(msg["content"])

    # === 核心逻辑：处理输入 (包括输入框和按钮点击) ===
    
    # 1. 检查是否有来自按钮点击的预设问题
    preset_query = st.session_state.next_query
    user_input = st.chat_input("请输入问题...")

    # 2. 决定最终使用的 query
    final_query = None
    if user_input:
        final_query = user_input
        st.session_state.next_query = "" # 清空预设
    elif preset_query:
        final_query = preset_query
        st.session_state.next_query = "" # 消费掉预设，防止循环

    # 3. 执行对话逻辑
    if final_query:
        if not st.session_state.selected_kbs:
            st.error("请选择知识库！")
            return

        with st.spinner("加载索引..."):
            source_documents, vector_store = load_kbs(st.session_state.selected_kbs)

        # 添加用户消息
        st.session_state.messages.append({"role": "user", "content": final_query})
        with st.chat_message("user"):
            st.markdown(final_query)

        # 初始化 State
        initial_state = {
            "messages": [HumanMessage(content=final_query)],
            "source_documents": source_documents,
            "vector_store": vector_store,
            "next": "Supervisor",
            "current_search_query": "",
            "final_evidence": [],
            "loop_count": 0,
            "attempted_searches": [],
            "research_notes": [],
            "failed_topics": []
        }

        with st.chat_message("assistant"):
            # 状态容器
            status_container = st.status("🕵️‍♂️ Agent 正在深度调研...", expanded=True)
            final_answer = ""

            try:
                # 增加递归限制防止报错
                graph_config = {"recursion_limit": 50}
                
                for step in graph.stream(initial_state, config=graph_config):
                    for node_name, update in step.items():
                        if node_name == "Supervisor":
                            next_node = update.get("next")
                            query = update.get("current_search_query")
                            loop = update.get("loop_count", 0)
                            
                            if next_node == "Searcher":
                                status_container.write(f"🔄 **第 {loop} 轮调研**: 发现缺口，指派搜索 `{query}`")
                            elif next_node == "Answerer":
                                status_container.write("✅ **决策**: 信息充足，正在撰写报告...")

                        elif node_name == "Searcher":
                            msgs = update.get("messages", [])
                            if msgs:
                                with status_container.expander(f"🔍 检索报告: {update.get('attempted_searches', [''])[0]}", expanded=False):
                                    st.markdown(msgs[-1].content)

                        elif node_name == "Answerer":
                            msgs = update.get("messages", [])
                            if msgs:
                                final_answer = msgs[-1].content

                status_container.update(label="回答完成", state="complete", expanded=False)
                
                if final_answer:
                    # 保存到历史
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})
                    # 渲染当前回答 (使用优化后的格式化函数)
                    format_display_message(final_answer)

            except Exception as e:
                status_container.update(label="Error", state="error")
                st.error(f"运行错误: {e}")


def main():
    with st.sidebar:
        st.title("DeepSeek RAG")
        page = st.radio("导航", ["💬 对话", "⚙️ 知识库"], index=0)

    if page == "💬 对话":
        render_chat()
    else:
        render_kb_management()


if __name__ == "__main__":
    main()