# frontend/views/deep_read.py
import streamlit as st
import tempfile
import os
from langchain_community.document_loaders import PyPDFLoader

# === 修改点：引用正确的图 ===
from src.graphs.deep_read_graph import deep_read_graph
# ==========================

from src.db import init_db, create_session, save_report, get_all_reports, get_report_content, delete_report
from src.nodes.common import get_llm
# === [修改] 适配 Langfuse v3 ===
try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:
    LangfuseCallbackHandler = None

# 初始化数据库
init_db()

def load_file_content(uploaded_file) -> str:
    """提取文件文本"""
    file_ext = uploaded_file.name.split(".")[-1].lower()
    full_text = ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    try:
        if file_ext == "pdf":
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            full_text = "\n\n".join([p.page_content for p in pages])
        else:
            with open(tmp_path, "r", encoding="utf-8") as f:
                full_text = f.read()
    except Exception: pass
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)
    return full_text

def render():
    st.header("🧠 全文深度解读")
    
    # 侧边栏
    with st.sidebar:
        st.markdown("---")
        st.subheader("📜 历史报告")
        history_reports = get_all_reports()
        if not history_reports:
            st.caption("暂无历史记录")
        for rep in history_reports:
            col1, col2 = st.columns([5, 1])
            with col1:
                if st.button(f"📄 {rep['title']}", key=f"hist_{rep['id']}", help=f"来源: {rep['source_name']}"):
                    full_data = get_report_content(rep['id'])
                    if full_data:
                        st.session_state.deep_state = "done"
                        st.session_state.final_report = full_data['content']
                        st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_rep_{rep['id']}"):
                    delete_report(rep['id'])
                    st.rerun()

    if "deep_state" not in st.session_state:
        st.session_state.deep_state = "idle"

    # 输入区域
    input_mode = st.radio("选择输入来源", ["📁 上传文件", "📝 粘贴文本"], horizontal=True, label_visibility="collapsed")
    st.markdown("---")

    uploaded_file = None
    text_input = ""
    source_name = "Unknown"

    if input_mode == "📁 上传文件":
        uploaded_file = st.file_uploader("上传 PDF 或 TXT 文档", type=["pdf", "txt"], key="deep_upload")
        if uploaded_file: source_name = uploaded_file.name
    else:
        text_input = st.text_area("直接粘贴文本内容", height=300)
        if text_input: source_name = f"文本: {text_input[:30]}..."

    start_disabled = not (uploaded_file or (text_input and len(text_input.strip()) > 50))

    if st.button("🚀 开始深度解读", type="primary", disabled=start_disabled):
        st.session_state.deep_state = "running"
        st.session_state.final_report = ""
        st.session_state.deep_logs = [] # 初始化日志
        
        full_text_content = ""
        with st.spinner("正在提取并缓存全文..."):
            if uploaded_file:
                full_text_content = load_file_content(uploaded_file)
            elif text_input:
                full_text_content = text_input
        
        if not full_text_content:
            st.error("内容为空")
            return

        # 初始化状态，符合 AgentState 定义
        st.session_state.deep_input = {
            "messages": [], 
            "full_content": full_text_content, 
            "doc_title": source_name,
            "next": "Planner", 
            "loop_count": 0, 
            "qa_pairs": [], 
            "current_question": "", 
            "final_report": "",
            # 补全 AgentState 缺少的字段防止报错
            "user_goal": "", 
            "suggested_questions": [], 
            "source_documents": [], 
            "vector_store": None,
            "current_search_query": "", 
            "final_evidence": [], 
            "attempted_searches": [], 
            "failed_topics": [], 
            "research_notes": []
        }
        st.rerun()

    # 运行展示区域
    if st.session_state.deep_state == "running":
        status_box = st.status("🕵️‍♂️ DeepSeek 深度思考中...", expanded=True)
        final_report = ""
        
        try:
            # === [修改] 注入 Callback ===
            run_config = {"recursion_limit": 50}
            if LangfuseCallbackHandler:
                handler = LangfuseCallbackHandler()
                run_config["callbacks"] = [handler]
                run_config["metadata"] = {
                    "langfuse_tags": ["deep-read"]
                }

            for step in deep_read_graph.stream(st.session_state.deep_input, config=run_config):
                for node, update in step.items():
                    if node == "Planner":
                        question = update.get("current_question")
                        if question:
                            status_box.write(f"🤔 **Planner**: 发现盲点，正在追问：`{question}`")
                        else:
                            status_box.write("✅ **Planner**: 核心信息收集完毕...")
                            
                    elif node == "Researcher":
                        qa_pairs = update.get("qa_pairs", [])
                        if qa_pairs:
                            # 提取最新的 QA 显示
                            latest = qa_pairs[-1]
                            ans_preview = latest.split("**A**:")[-1][:50] + "..." if "**A**:" in latest else "..."
                            status_box.write(f"📚 **Researcher**: 已查证 - {ans_preview}")
                    
                    elif node == "Writer":
                        status_box.write("✍️ **Writer**: 正在撰写《深度解读报告》主体部分...")
                        final_report = update.get("final_report")
                    
                    elif node == "Outlooker":
                        status_box.write("🔭 **Outlooker**: 正在补充扩展思考...")
                        final_report = update.get("final_report")

            status_box.update(label="解读完成！已自动保存。", state="complete", expanded=False)
            st.session_state.final_report = final_report
            st.session_state.deep_state = "done"
            
            # 自动保存
            doc_title = st.session_state.deep_input.get("doc_title", "未命名")
            save_report(f"解读: {doc_title}", doc_title, final_report)
            st.rerun()
            
        except Exception as e:
            st.error(f"运行出错: {e}")
            st.session_state.deep_state = "idle"

    # 结果展示区域
    if st.session_state.deep_state == "done" and st.session_state.final_report:
        st.divider()
        st.subheader("📝 深度解读报告")
        st.markdown(st.session_state.final_report)
        st.divider()
        if st.button("🔙 返回首页"):
            st.session_state.deep_state = "idle"
            st.rerun()