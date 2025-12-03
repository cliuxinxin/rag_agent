# ./frontend/app.py
import sys
import os
import re
import html
import yaml
import streamlit as st
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents
from src.storage import save_kb, load_kbs, list_kbs, delete_kb, get_kb_details
# 引入数据库模块
from src.db import init_db, create_session, get_all_sessions, get_messages, add_message, delete_session, update_session_title
# 引入数据库新函数
from src.db import save_report, get_all_reports, get_report_content, delete_report
# 引入新的 DB 函数
from src.db import save_session_artifact, get_session_artifact, update_session_qa_pairs
# 引入新的 DB 函数 (写作模式)
from src.db import create_writing_project, get_writing_project, update_project_outline, update_project_draft, get_all_projects, delete_project
# 引入 LLM 获取函数用于生成标题
from src.nodes import get_llm
# 引入深度解读模块
from src.deep_flow import deep_graph, deep_qa_graph
# 引入深度写作模块
from src.write_flow import outline_graph, refine_graph, writing_graph
# 引入 TextLoader 和 PyPDFLoader 仅用于提取文本，不做切片
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import tempfile
import json  # 用于处理 JSON 数据
import time  # 用于添加延迟

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Pro", layout="wide", page_icon="🕵️‍♂️")

# 初始化数据库
init_db()

# === 全局 CSS 样式优化 ===
st.markdown("""
<style>
    /* 全局字体优化 */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* 引用 tooltip 样式 */
    .ref-container {
        position: relative;
        display: inline-block;
        color: #1f77b4;
        font-weight: bold;
        cursor: help;
        border-bottom: 1px dashed #1f77b4;
    }
    .ref-container .ref-tooltip {
        visibility: hidden;
        width: 320px;
        background-color: #ffffff;
        color: #31333F;
        text-align: left;
        border: 1px solid #e0e0e0;
        padding: 12px;
        border-radius: 8px;
        position: absolute;
        z-index: 99999;
        bottom: 120%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        transition: opacity 0.2s;
        font-weight: normal;
        font-size: 14px;
        line-height: 1.5;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.15);
        white-space: normal;
        pointer-events: none;
    }
    .ref-container:hover .ref-tooltip {
        visibility: visible;
        opacity: 1;
    }
    .ref-container .ref-tooltip::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -6px;
        border-width: 6px;
        border-style: solid;
        border-color: #ffffff transparent transparent transparent;
    }

    /* === 侧边栏样式重构 === */
    
    /* 隐藏 Streamlit 默认的 deploy 按钮 */
    .stDeployButton {display: none;}
    
    /* 侧边栏按钮基础样式 */
    section[data-testid="stSidebar"] button {
        border: none !important;
        text-align: left !important;
        transition: background-color 0.2s;
        padding-left: 10px !important;
    }
    
    /* 历史记录按钮样式 (非活跃) */
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
        background-color: transparent !important;
        color: #555 !important;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
        background-color: #f0f2f6 !important;
        color: #000 !important;
    }

    /* 删除按钮微调 */
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button[help="删除此对话"] {
        color: #999 !important;
        padding: 0px !important;
        text-align: center !important;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button[help="删除此对话"]:hover {
        color: #ff4b4b !important;
        background-color: #ffeaea !important;
    }

    /* 新建对话按钮 */
    .new-chat-btn button {
        border: 1px solid #e0e0e0 !important;
        text-align: center !important;
        background-color: white !important;
    }
    
</style>
""", unsafe_allow_html=True)

# === 初始化 Session State ===
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

for key in ["selected_kbs", "next_query", "attempted_searches", "research_notes", "failed_topics"]:
    if key not in st.session_state:
        if key == "next_query": st.session_state[key] = ""
        else: st.session_state[key] = []

if "messages" not in st.session_state:
    st.session_state.messages = []

# === 辅助功能 ===

def generate_smart_title(query, answer):
    """使用 LLM 生成简短的会话标题"""
    try:
        llm = get_llm()
        prompt = f"""
        请根据以下对话内容，生成一个非常简短的标题（5-10个字以内），用于历史记录列表。
        不要使用引号，直接输出标题文本。
        
        用户: {query[:200]}
        AI: {answer[:200]}
        """
        response = llm.invoke([SystemMessage(content=prompt)])
        title = response.content.strip().replace('"', '').replace('《', '').replace('》', '')
        return title if len(title) < 15 else title[:15]
    except:
        return query[:10] + "..."

def format_display_message(content):
    split_markers = ["【🕵️‍♂️ 调查笔记】", "【📚 原始片段】", "【原始知识库片段】"]
    split_index = -1
    for marker in split_markers:
        idx = content.find(marker)
        if idx != -1:
            if split_index == -1 or idx < split_index:
                split_index = idx
    
    main_text = content
    ref_text = ""
    if split_index != -1:
        main_text = content[:split_index]
        ref_text = content[split_index:]

    ref_map = {}
    if ref_text:
        matches = re.findall(r"\[Ref\s*(\d+)\]\s*(.*?)(?=\n|\[Ref|\Z)", ref_text, re.DOTALL)
        for ref_id, ref_content in matches:
            clean_content = ref_content.strip().lstrip('>').strip()[:350] 
            if len(ref_content) > 350: clean_content += "..."
            if clean_content: ref_map[ref_id] = clean_content

    def replace_ref(match):
        ref_id = match.group(1)
        tooltip_text = ref_map.get(ref_id, "详情请查看底部折叠区域")
        html_snippet = f'''
        <span class="ref-container" title="{html.escape(tooltip_text)}">
            [Ref {ref_id}]
            <span class="ref-tooltip">{html.escape(tooltip_text)}</span>
        </span>
        '''
        return html_snippet.replace('\n', '')

    enhanced_main_text = re.sub(r"\[Ref\s*(\d+)\]", replace_ref, main_text)
    st.markdown(enhanced_main_text, unsafe_allow_html=True)
    
    if ref_text:
        with st.expander("📚 查看调查笔记与原始引用 (点击展开)", expanded=False):
            st.markdown(ref_text)

    suggestions = re.findall(r"(?:\[点击\]|\[Click\])\s*(.*)", content)
    if not suggestions:
         suggestions = re.findall(r"\d+\.\s+(.*)\?", content)

    if suggestions:
        st.markdown("---")
        st.caption("👉 **您可以点击以下问题继续追问：**")
        cols = st.columns(len(suggestions))
        for idx, question in enumerate(suggestions):
            q_text = question.strip()
            if cols[idx].button(q_text, key=f"sugg_{hash(content)}_{idx}"):
                st.session_state.next_query = q_text
                st.rerun()

# === 辅助函数：只读文本，不切片 ===
def load_file_content(uploaded_file) -> str:
    """直接读取文件全文内容"""
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
            # 假设是 txt
            with open(tmp_path, "r", encoding="utf-8") as f:
                full_text = f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return full_text

# === 渲染深度模式 ===
def render_deep_read_mode():
    st.header("🧠 全文深度解读 (Full Context)")
    
    # === 1. 侧边栏：历史报告 (保持不变) ===
    with st.sidebar:
        st.markdown("---")
        st.subheader("📜 历史报告")
        history_reports = get_all_reports()
        
        if not history_reports:
            st.caption("暂无历史记录")
        
        for rep in history_reports:
            col1, col2 = st.columns([5, 1])
            with col1:
                # 点击标题加载报告
                if st.button(f"📄 {rep['title']}", key=f"hist_{rep['id']}", help=f"来源: {rep['source_name']}"):
                    full_data = get_report_content(rep['id'])
                    if full_data:
                        st.session_state.deep_state = "done"
                        st.session_state.final_report = full_data['content']
                        st.rerun()
            with col2:
                # 删除按钮
                if st.button("🗑️", key=f"del_rep_{rep['id']}", help="删除此记录"):
                    delete_report(rep['id'])
                    st.rerun()

    # === 2. 主界面：输入方式选择 (UI 优化：改用 Radio 防止 Tab 跳转) ===
    # 初始化变量，防止未定义错误
    uploaded_file = None
    text_input = ""
    source_name = "Unknown"
    
    # 使用 Radio 横向排列代替 Tabs，这样 selection 会被 session_state 记住，不会跳动
    input_mode = st.radio(
        "选择输入来源", 
        ["📁 上传文件", "📝 粘贴文本"], 
        horizontal=True, 
        label_visibility="collapsed" # 隐藏标题，使其看起来像 Tab 栏
    )
    st.markdown("---") # 加一条分割线，视觉上区分区域

    if input_mode == "📁 上传文件":
        uploaded_file = st.file_uploader("上传 PDF 或 TXT 文档", type=["pdf", "txt"], key="deep_upload")
        if uploaded_file:
            source_name = uploaded_file.name

    else: # 模式为 "📝 粘贴文本"
        text_input = st.text_area("直接粘贴文本内容", height=300, placeholder="在此处粘贴论文全文、合同或长文章...")
        if text_input:
            source_name = "Text Input"
            # 简单的标题提取：取前20个字
            if len(text_input) > 0:
                clean_title = text_input[:30].replace("\n", " ").strip()
                source_name = f"文本: {clean_title}..."

    # 确定输入源 (保持原有逻辑)
    start_disabled = True
    if uploaded_file or (text_input and len(text_input.strip()) > 50):
        start_disabled = False

    if "deep_state" not in st.session_state:
        st.session_state.deep_state = "idle"

    # === 3. 开始按钮 (保持不变) ===
    if st.button("🚀 开始深度解读", type="primary", disabled=start_disabled):
        st.session_state.deep_state = "running"
        st.session_state.deep_logs = []
        st.session_state.final_report = ""
        
        # 提取文本内容
        full_text_content = ""
        with st.spinner("正在提取并缓存全文..."):
            if uploaded_file:
                # 复用之前的 load_file_content 函数
                full_text_content = load_file_content(uploaded_file)
            elif text_input:
                full_text_content = text_input
        
        if not full_text_content:
            st.error("内容为空，无法处理。")
            return

        # 初始化图状态
        initial_input = {
            "messages": [],
            "full_content": full_text_content,
            "doc_title": source_name,
            "next": "Planner",
            "loop_count": 0,
            "qa_pairs": [],
            "current_question": "",
            "final_report": ""
        }
        st.session_state.deep_input = initial_input
        st.rerun()

    # === 4. 运行状态显示 ===
    if st.session_state.deep_state == "running":
        status_box = st.status("🕵️‍♂️ DeepSeek 深度思考中...", expanded=True)
        final_report = ""
        
        try:
            for step in deep_graph.stream(st.session_state.deep_input, config={"recursion_limit": 50}):
                for node, update in step.items():
                    if node == "Planner":
                        question = update.get("current_question")
                        if question:
                            status_box.write(f"🤔 **Planner**: 发现盲点，正在追问：`{question}`")
                        else:
                            status_box.write("✅ **Planner**: 核心信息收集完毕，转交 Writer 撰写初稿...")
                            
                    elif node == "Researcher":
                        qa_pairs = update.get("qa_pairs", [])
                        if qa_pairs:
                            latest_qa = qa_pairs[-1]
                            try:
                                q_part = latest_qa.split("**A**:")[0].replace("❓ **Q**:", "").strip()
                                a_part = latest_qa.split("**A**:")[1].strip()
                            except:
                                q_part = "细节查询"
                                a_part = latest_qa
                            
                            with status_box.expander(f"📚 Researcher 已调研: {q_part[:30]}...", expanded=False):
                                st.markdown(a_part)
                    
                    elif node == "Writer":
                        status_box.write("✍️ **Writer**: 正在撰写《深度解读报告》主体部分...")
                        final_report = update.get("final_report")
                    
                    elif node == "Outlooker":
                        status_box.write("🔭 **Outlooker**: 正在分析扩展研究方向与行动指南...")
                        final_report = update.get("final_report") # 获取追加后的完整报告

            status_box.update(label="解读完成！已自动保存。", state="complete", expanded=False)
            st.session_state.final_report = final_report
            st.session_state.deep_state = "done"
            
            # === 自动保存到数据库 ===
            # 生成一个简短标题，例如 "解读: {原文件名}"
            doc_title = st.session_state.deep_input.get("doc_title", "未命名文档")
            report_title = f"解读: {doc_title}"
            save_report(report_title, doc_title, final_report)
            st.toast("✅ 报告已保存至历史记录")
            
            st.rerun()
            
        except Exception as e:
            st.error(f"运行出错: {e}")
            st.session_state.deep_state = "idle"

    # === 5. 结果展示 ===
    if st.session_state.deep_state == "done" and st.session_state.final_report:
        st.divider()
        st.subheader("📝 深度解读报告")
        
        # 直接显示报告，不需要任何复杂的解析
        st.markdown(st.session_state.final_report)
        
        st.divider()
        if st.button("🔙 返回首页"):
            st.session_state.deep_state = "idle"
            st.rerun()

# === 新增：深度对话模式 ===
def render_deep_qa_mode():
    # === 1. 侧边栏：会话管理 ===
    with st.sidebar:
        st.header("🗂️ 追问会话")
        
        # 新建会话按钮
        if st.button("➕ 新建文档追问", use_container_width=True, type="primary"):
            new_id = create_session("未命名追问")
            st.session_state.current_session_id = new_id
            st.rerun()
            
        st.markdown("---")
        
        # 列出所有会话
        # 注意：这里简单的列出所有 session。
        # 实际体验中，你可能想只列出有过 Artifact 的 session，或者混在一起。
        # 这里为了保持一致性，我们复用通用的 session 列表逻辑
        sessions = get_all_sessions()
        
        for s in sessions:
            is_active = (s['id'] == st.session_state.current_session_id)
            btn_type = "primary" if is_active else "secondary"
            
            # 检查这个 session 是否有 Deep QA 的数据 (Artifact)
            # 这是一个轻量级查询，为了图标区分
            # (在生产环境中建议优化，比如在 sessions 表加 type 字段)
            artifact = get_session_artifact(s['id'])
            icon = "🕵️‍♂️" if artifact else "📝"
            
            col1, col2 = st.columns([5, 1])
            with col1:
                if st.button(f"{icon} {s['title']}", key=f"sess_qa_{s['id']}", use_container_width=True, type=btn_type):
                    st.session_state.current_session_id = s['id']
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_qa_{s['id']}"):
                    delete_session(s['id'])
                    if st.session_state.current_session_id == s['id']:
                        st.session_state.current_session_id = None
                    st.rerun()

    # === 2. 主区域逻辑 ===
    st.title("❓ 深度追问模式")
    
    # 如果没有选中会话，提示新建
    if not st.session_state.current_session_id:
        st.info("👈 请在左侧新建会话或选择已有会话。")
        return

    current_session_id = st.session_state.current_session_id
    
    # 尝试加载当前会话的 Artifact (文档和记忆)
    artifact = get_session_artifact(current_session_id)
    
    # 场景 A: 新会话，还没有上传文档 -> 显示上传界面 (在右侧/主区域)
    if not artifact:
        st.markdown("### 1️⃣ 第一步：请提供深度分析的素材")
        
        with st.container(border=True):
            tab1, tab2 = st.tabs(["📁 上传文档", "📝 粘贴文本"])
            
            full_content = ""
            doc_title = ""
            
            with tab1:
                uploaded_file = st.file_uploader("支持 PDF/TXT", type=["pdf", "txt"], key="new_qa_upload")
                if uploaded_file:
                    doc_title = uploaded_file.name
                    if st.button("确认上传并开始", key="btn_upload"):
                        full_content = load_file_content(uploaded_file)

            with tab2:
                text_input = st.text_area("输入长文本", height=200)
                if text_input and st.button("确认提交文本", key="btn_paste"):
                    doc_title = f"文本: {text_input[:15]}..."
                    full_content = text_input
            
            # 处理保存
            if full_content:
                # 1. 保存到 DB
                save_session_artifact(current_session_id, doc_title, full_content, [])
                # 2. 更新会话标题
                update_session_title(current_session_id, f"追问: {doc_title}")
                # 3. 刷新页面进入聊天模式
                st.rerun()
                
    # 场景 B: 已有文档 -> 显示聊天界面
    else:
        doc_title = artifact['doc_title']
        full_content = artifact['doc_content']
        qa_pairs_history = artifact['qa_pairs'] # 这是一个 List[str]
        
        # --- 顶部：文档状态栏 ---
        with st.expander(f"📄 当前文档: {doc_title} (点击查看全文)", expanded=False):
            st.text_area("文档内容", full_content, height=200, disabled=True)
            # 提供一个重新上传的入口（可选）
            if st.button("⚠️ 替换文档 (这将清空当前推理记忆)"):
                # 这里的逻辑可以是清空 artifact，或者跳转回上传页
                # 简单做法：清空 artifact table 该行
                # delete_session_artifact(current_session_id) # 需要实现这个函数
                pass 

        # --- 聊天区域 ---
        
        # 1. 加载消息历史 (从 messages 表)
        messages = get_messages(current_session_id)
        
        # 渲染历史消息
        for msg in messages:
            with st.chat_message(msg["role"]):
                # 如果是 AI 的消息，且包含 thoughts (我们需要一种方式存储 thoughts)
                # 简单方案：thoughts 直接拼在 content 里，用特定标记分隔，渲染时拆分
                # 或者：只显示最终结果，Deep QA 的过程比较长，不建议存 DB 太乱
                # 这里我们假设 messages 表里存的是最终展示用的 markdown
                format_display_message(msg["content"]) # 复用之前的格式化函数支持 tooltip

        # 2. 输入区域
        user_input = st.chat_input("针对文档提问...")
        
        # 3. 处理逻辑
        if user_input:
            # 显示用户消息
            with st.chat_message("user"):
                st.markdown(user_input)
            
            # 存入 DB
            add_message(current_session_id, "user", user_input)
            
            # 构造 Agent State
            # 关键：从 artifact 中恢复 qa_pairs，这样 Agent 就有记忆了！
            initial_state = {
                "messages": [], # 这里放 Graph 需要的消息，通常为空即可，主要靠 qa_pairs
                "full_content": full_content,
                "doc_title": doc_title,
                "user_goal": user_input,
                "qa_pairs": qa_pairs_history, # <--- 注入记忆
                "loop_count": 0,
                "current_question": "",
                "final_report": "",
                "suggested_questions": []
            }
            
            with st.chat_message("assistant"):
                status_box = st.status("🕵️‍♂️ DeepSeek 正在深度查证...", expanded=True)
                response_placeholder = st.empty()
                full_response = ""
                thought_log = ""
                
                try:
                    # 运行 Graph
                    final_qa_pairs = qa_pairs_history # 默认它是旧的，等运行完更新
                    
                    for step in deep_qa_graph.stream(initial_state, config={"recursion_limit": 50}):
                        for node, update in step.items():
                            
                            # 获取最新的 qa_pairs (如果有更新)
                            if "qa_pairs" in update:
                                final_qa_pairs = update["qa_pairs"]
                            
                            if node == "QAPlanner":
                                q = update.get("current_question")
                                if q:
                                    msg = f"🤔 **规划**: 需要查证 `{q}`"
                                    status_box.write(msg)
                                    thought_log += f"\n\n> {msg}"
                                else:
                                    status_box.write("✅ **规划**: 信息充足，开始汇总。")

                            elif node == "Researcher":
                                # 取最新的一条展示
                                pairs = update.get("qa_pairs", [])
                                if pairs:
                                    latest = pairs[-1]
                                    if "**A**:" in latest:
                                        a_text = latest.split("**A**:")[1][:50] + "..."
                                        status_box.write(f"📚 **查证**: {a_text}")
                                        thought_log += f"\n\n> 📚 **查证**: {latest}"

                            elif node == "QAWriter":
                                full_response = update.get("final_report", "")
                                
                            elif node == "Suggester":
                                suggestions = update.get("suggested_questions", [])
                                if suggestions:
                                    full_response += "\n\n---\n👉 **建议追问：**\n"
                                    for s in suggestions:
                                        full_response += f"- {s}\n"

                    # 运行结束
                    status_box.update(label="完成", state="complete", expanded=False)
                    
                    # 拼接思考过程 (作为折叠块)
                    if thought_log:
                        final_content_to_show = f"{full_response}\n\n<details><summary>🧠 思考过程</summary>{thought_log}</details>"
                    else:
                        final_content_to_show = full_response
                        
                    response_placeholder.markdown(final_content_to_show, unsafe_allow_html=True)
                    
                    # 4. 数据持久化
                    # (A) 保存 AI 回复到 messages 表
                    add_message(current_session_id, "assistant", final_content_to_show)
                    
                    # (B) 更新 qa_pairs 到 artifacts 表
                    update_session_qa_pairs(current_session_id, final_qa_pairs)
                    
                    # 刷新以显示新消息
                    st.rerun()
                    
                except Exception as e:
                    status_box.update(label="发生错误", state="error")
                    st.error(f"Error: {e}")

# === 新增：深度写作模式 ===
def render_deep_writing_mode():
    st.title("✍️ Agentic Deep Writing")
    
    # === 侧边栏：项目列表 ===
    with st.sidebar:
        st.subheader("📂 写作项目")
        if st.button("➕ 新建写作项目", use_container_width=True):
            st.session_state.current_project_id = None
            st.rerun()
            
        st.markdown("---")
        projects = get_all_projects()
        for p in projects:
            c1, c2 = st.columns([5, 1])
            with c1:
                if st.button(f"📄 {p['title']}", key=f"proj_{p['id']}", use_container_width=True):
                    st.session_state.current_project_id = p['id']
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"del_proj_{p['id']}"):
                    delete_project(p['id'])
                    if st.session_state.get("current_project_id") == p['id']:
                        st.session_state.current_project_id = None
                    st.rerun()

    # === 主区域逻辑 ===
    
    # 场景 1: 新建项目
    if not st.session_state.get("current_project_id"):
        st.subheader("🚀 开始新的写作")
        
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("项目标题", placeholder="例如：2025年AI行业发展报告")
        
        req = st.text_area("写作需求/Prompt", height=150, placeholder="例如：写一篇关于 DeepSeek 技术的深度分析文章，受众是技术人员，风格专业严谨。")
        
        source_type = st.radio("参考资料来源", ["知识库 (KB)", "直接粘贴文本", "上传文件"], horizontal=True)
        
        kb_names = []
        source_data = ""
        
        if source_type == "知识库 (KB)":
            all_kbs = list_kbs()
            if not all_kbs:
                st.warning("暂无可用知识库，请先创建。")
            else:
                kb_names = st.multiselect("选择知识库", all_kbs)
                
        elif source_type == "直接粘贴文本":
            source_data = st.text_area("粘贴文本内容", height=200)
            
        elif source_type == "上传文件":
            uploaded_file = st.file_uploader("上传 PDF 或 TXT 文档", type=["pdf", "txt"])
            if uploaded_file:
                source_data = load_file_content(uploaded_file)
        
        start_disabled = not (title and req and (kb_names or source_data))
        
        if st.button("🚀 生成大纲", type="primary", disabled=start_disabled):
            with st.spinner("正在生成大纲..."):
                # 创建项目
                project_id = create_writing_project(
                    title=title,
                    requirements=req,
                    source_type="kb" if source_type == "知识库 (KB)" else "text" if source_type == "直接粘贴文本" else "file",
                    source_data=json.dumps(kb_names) if source_type == "知识库 (KB)" else source_data
                )
                
                # 准备初始状态
                initial_state = {
                    "project_id": project_id,
                    "user_requirement": req,
                    "source_content": source_data if source_type != "知识库 (KB)" else "",
                    "kb_names": kb_names if source_type == "知识库 (KB)" else [],
                    "messages": [],
                    "loop_count": 0,
                    "current_question": "",
                    "qa_pairs": [],
                    "research_report": "",
                    "current_outline": [],
                    "next": "Planner"
                }
                
                # 运行图生成大纲
                for step in outline_graph.stream(initial_state):
                    pass  # 图会自动运行直到结束
                
                # 获取结果并保存
                final_state = initial_state
                update_project_outline(project_id, final_state["current_outline"], final_state["research_report"])
                
                # 设置当前项目ID并刷新页面
                st.session_state.current_project_id = project_id
                st.rerun()
    
    # 场景 2: 编辑现有项目
    else:
        project_id = st.session_state.current_project_id
        project_data = get_writing_project(project_id)
        
        if not project_data:
            st.error("项目不存在")
            st.session_state.current_project_id = None
            st.rerun()
            return
            
        st.subheader(f"📝 {project_data['title']}")
        
        # 同样使用 Tabs，但逻辑增强
        tab_outline, tab_write, tab_preview = st.tabs(["📊 策划与大纲", "✍️ 迭代写作", "👀 全文预览"])
        
        # --- TAB 1: 策划与大纲 ---
        with tab_outline:
            col_rep, col_out = st.columns([1, 1])
            
            # 左侧：调研报告
            with col_rep:
                st.subheader("📑 调研报告")
                st.info("这是 AI 基于你的需求和知识库生成的写作蓝图。")
                report_content = st.text_area("调研报告内容", value=project_data['research_report'], height=600)
                
                # 允许手动修改报告
                if report_content != project_data['research_report']:
                    if st.button("💾 保存报告修改"):
                        update_project_outline(project_id, project_data['outline_data'], report_content)
                        st.success("报告已更新")
                        st.rerun()

            # 右侧：大纲编辑
            with col_out:
                st.subheader("📝 结构大纲")
                outline = project_data['outline_data']
                new_outline = []
                has_change = False
                
                # 渲染可编辑大纲
                for i, section in enumerate(outline):
                    with st.expander(f"第 {i+1} 章: {section['title']}", expanded=False):
                        new_title = st.text_input("标题", value=section['title'], key=f"t_{i}")
                        new_desc = st.text_area("指导/要点", value=section['desc'], key=f"d_{i}")
                        
                        if new_title != section['title'] or new_desc != section['desc']:
                            has_change = True
                            
                        new_outline.append({"title": new_title, "desc": new_desc, "content": section.get("content", "")})
                
                # 大纲操作区
                st.markdown("---")
                if st.button("➕ 添加新章节"):
                    new_outline.append({"title": "新章节", "desc": "请输入内容要点", "content": ""})
                    has_change = True
                    
                if has_change or len(new_outline) != len(outline):
                    if st.button("💾 保存大纲并同步更新报告", type="primary"):
                        with st.spinner("正在根据新大纲校准调研报告..."):
                            # 1. 保存大纲
                            update_project_outline(project_id, new_outline)
                            
                            # 2. 调用 report_update_graph
                            state = {
                                "research_report": project_data['research_report'],
                                "current_outline": new_outline
                            }
                            
                            # 运行图更新报告
                            for step in report_update_graph.stream(state):
                                pass
                            
                            # 保存更新后的报告
                            update_project_outline(project_id, new_outline, state["research_report"])
                            
                            st.success("大纲和调研报告已同步更新！")
                            st.rerun()
        
        # --- TAB 2: 迭代写作 ---
        with tab_write:
            st.subheader("✍️ 分章节写作")
            
            if not project_data['outline_data']:
                st.info("请先生成大纲")
                return
                
            outline = project_data['outline_data']
            generated_content = project_data.get('full_draft', '')
            
            # 显示已生成的内容
            if generated_content:
                with st.expander("已生成全文（点击展开）", expanded=False):
                    st.text_area("全文内容", generated_content, height=300, disabled=True)
            
            # 选择要写的章节
            chapter_options = [f"{i+1}. {sec['title']}" for i, sec in enumerate(outline)]
            selected_chapter = st.selectbox("选择要写的章节", chapter_options)
            selected_idx = chapter_options.index(selected_chapter)
            
            # 显示章节指导
            st.markdown(f"**章节指导**: {outline[selected_idx]['desc']}")
            
            # 生成按钮
            if st.button("🤖 AI 生成此章节"):
                with st.spinner(f"正在生成 {outline[selected_idx]['title']}..."):
                    # 准备状态
                    initial_state = {
                        "user_requirement": project_data['requirements'],
                        "research_report": project_data['research_report'],
                        "current_outline": outline,
                        "current_section_index": selected_idx,
                        "generated_content": generated_content,
                        "current_section_draft": "",
                        "next": "Writer"
                    }
                    
                    # 运行图生成章节
                    for step in writing_graph.stream(initial_state):
                        pass
                    
                    # 获取生成的内容
                    draft = initial_state["current_section_draft"]
                    
                    # 更新大纲中的章节内容
                    outline[selected_idx]["content"] = draft
                    update_project_outline(project_id, outline)
                    
                    # 更新全文草稿
                    # 这里简单处理，实际应该更精确地管理各章节内容
                    full_draft = ""
                    for sec in outline:
                        if sec["content"]:
                            full_draft += f"## {sec['title']}\n\n{sec['content']}\n\n"
                    update_project_draft(project_id, full_draft)
                    
                    st.success("章节生成完成！")
                    st.rerun()
            
            # 显示已生成的章节内容
            if outline[selected_idx].get("content"):
                st.markdown("### 已生成内容")
                st.markdown(outline[selected_idx]["content"])
        
        # --- TAB 3: 全文预览 ---
        with tab_preview:
            st.subheader("👀 全文预览")
            
            full_draft = project_data.get('full_draft', '')
            if full_draft:
                st.markdown(full_draft)
            else:
                st.info("暂无完整草稿，请先生成章节内容。")

# === 知识库管理界面 (保持不变) ===
def render_kb_management():
    st.header("📂 知识库管理")
    tabs = st.tabs(["📚 知识库列表 & 检视", "➕ 新建/追加知识"])
    
    with tabs[0]:
        existing_kbs = list_kbs()
        if not existing_kbs:
            st.info("暂无知识库。")
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
            chunks = split_documents(raw_docs, chunk_size=800)
            st.info(f"已切分为 {len(chunks)} 个片段 (Chunk Size=800)")
            progress_bar = st.progress(0, text="初始化向量化...")
            try:
                save_kb(target_kb_name, chunks, language=kb_language, progress_bar=progress_bar)
                st.success("✅ 保存成功！")
                st.rerun()
            except Exception as e:
                st.error(f"保存失败: {e}")

# === 侧边栏历史记录管理 (UI 优化版) ===
def render_history_sidebar():
    st.markdown("### 💬 聊天历史")
    
    # 新建对话按钮
    with st.container():
        st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
        if st.button("➕ 开启新对话", use_container_width=True, type="primary"):
            new_id = create_session()
            st.session_state.current_session_id = new_id
            st.session_state.messages = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    sessions = get_all_sessions()
    
    # 自动加载逻辑
    if st.session_state.current_session_id is None:
        if sessions:
            st.session_state.current_session_id = sessions[0]['id']
            st.session_state.messages = get_messages(sessions[0]['id'])
        else:
            new_id = create_session()
            st.session_state.current_session_id = new_id
            st.session_state.messages = []
    
    # 渲染列表
    scroll_container = st.container(height=500, border=False)
    with scroll_container:
        for s in sessions:
            is_selected = (s['id'] == st.session_state.current_session_id)
            
            # 使用列布局：左边是标题按钮，右边是删除按钮
            col1, col2 = st.columns([5, 1])
            
            with col1:
                # 选中的会话使用 primary 样式，其他的用 secondary (CSS 会处理成透明背景)
                btn_type = "primary" if is_selected else "secondary"
                icon = "📂" if is_selected else "🗨️"
                
                if st.button(f"{icon} {s['title']}", key=f"sess_{s['id']}", use_container_width=True, type=btn_type):
                    st.session_state.current_session_id = s['id']
                    st.session_state.messages = get_messages(s['id'])
                    st.rerun()
            
            with col2:
                if st.button("🗑️", key=f"del_{s['id']}", help="删除此对话"):
                    delete_session(s['id'])
                    # 如果删除的是当前会话，重置
                    if st.session_state.current_session_id == s['id']:
                        st.session_state.current_session_id = None
                        st.session_state.messages = []
                    st.rerun()

# === 聊天界面 ===
def render_chat():
    with st.sidebar:
        st.subheader("🧠 知识库选择")
        all_kbs = list_kbs()
        selected_kbs = st.multiselect("选择知识库", all_kbs, default=all_kbs[0] if all_kbs else None)
        st.session_state.selected_kbs = selected_kbs
        
        # 渲染历史记录
        render_history_sidebar()
    
    st.header("💬 DeepSeek Research Agent")
    
    # 显示当前会话标题
    if st.session_state.current_session_id:
        sessions = get_all_sessions()
        current_session = next((s for s in sessions if s['id'] == st.session_state.current_session_id), None)
        if current_session:
            st.subheader(f"当前会话: {current_session['title']}")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                format_display_message(msg["content"])
            else:
                st.markdown(msg["content"])
    
    preset_query = st.session_state.next_query
    user_input = st.chat_input("请输入问题...")
    
    final_query = None
    if user_input:
        final_query = user_input
        st.session_state.next_query = ""
    elif preset_query:
        final_query = preset_query
        st.session_state.next_query = ""
    
    if final_query:
        if not st.session_state.selected_kbs:
            st.error("请选择知识库！")
            return
        
        with st.spinner("加载索引..."):
            source_documents, vector_store = load_kbs(st.session_state.selected_kbs)
        
        st.session_state.messages.append({"role": "user", "content": final_query})
        # 保存用户消息到数据库
        if st.session_state.current_session_id:
            add_message(st.session_state.current_session_id, "user", final_query)
        
        with st.chat_message("user"):
            st.markdown(final_query)
        
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
            "failed_topics": [],
            # 深度解读专用字段（设置默认值）
            "full_content": "",
            "doc_title": "",
            "current_question": "",
            "qa_pairs": [],
            "final_report": ""
        }
        
        with st.chat_message("assistant"):
            status_container = st.status("🕵️‍♂️ Agent 正在深度调研...", expanded=True)
            final_answer = ""
            
            try:
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
                    # 保存助手消息到数据库
                    if st.session_state.current_session_id:
                        add_message(st.session_state.current_session_id, "assistant", final_answer)
                    
                    # 生成智能标题（仅在第一轮对话后）
                    if st.session_state.current_session_id and len(st.session_state.messages) == 2:
                        smart_title = generate_smart_title(final_query, final_answer)
                        update_session_title(st.session_state.current_session_id, smart_title)
                        # 更新界面显示
                        st.rerun()
                    
                    # 渲染当前回答 (使用优化后的格式化函数)
                    format_display_message(final_answer)
            
            except Exception as e:
                status_container.update(label="Error", state="error")
                st.error(f"运行错误: {e}")

# === 主程序 (适配 v0.4.x 最新版) ===
def main():
    try:
        with open('config.yaml') as file:
            config = yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("⚠️ 找不到 config.yaml，请先配置认证信息。")
        return
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config.get('preauthorized')
    )
    
    # 使用新的 API 方式进行登录
    authenticator.login()
    
    if st.session_state["authentication_status"]:
        authenticator.logout(location='sidebar')
        st.sidebar.write(f'欢迎 *{st.session_state["name"]}*')
        
        with st.sidebar:
            st.title("DeepSeek RAG")
            page = st.radio("导航", ["💬 对话", "🧠 深度解读", "❓ 深度追问", "✍️ 深度写作", "⚙️ 知识库"], index=0)
        
        if page == "💬 对话":
            render_chat()
        elif page == "🧠 深度解读":
            render_deep_read_mode()
        elif page == "❓ 深度追问":
            render_deep_qa_mode()
        elif page == "✍️ 深度写作":
            render_deep_writing_mode()
        else:
            render_kb_management()
    elif st.session_state["authentication_status"] is False:
        st.error('用户名或密码不正确')
    elif st.session_state["authentication_status"] is None:
        st.warning('请输入用户名和密码')

if __name__ == "__main__":
    main()