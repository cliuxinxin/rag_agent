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
from langchain_core.messages import HumanMessage, AIMessage

# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents
from src.storage import save_kb, load_kbs, list_kbs, delete_kb, get_kb_details

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Pro", layout="wide")

# === 全局 CSS 样式 (保持不变) ===
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

# === 初始化 Session State ===
for key in ["messages", "selected_kbs", "next_query", "attempted_searches", "research_notes", "failed_topics"]:
    if key not in st.session_state:
        if key == "messages": st.session_state[key] = []
        elif key == "next_query": st.session_state[key] = ""
        else: st.session_state[key] = []

# === 格式化函数 (保持不变) ===
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

# === 聊天界面 (保持不变) ===
def render_chat():
    with st.sidebar:
        st.divider()
        st.subheader("🧠 知识库选择")
        all_kbs = list_kbs()
        selected_kbs = st.multiselect("选择知识库", all_kbs, default=all_kbs[0] if all_kbs else None)
        st.session_state.selected_kbs = selected_kbs

    st.header("💬 DeepSeek Research Agent")

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
            "failed_topics": []
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
            page = st.radio("导航", ["💬 对话", "⚙️ 知识库"], index=0)

        if page == "💬 对话":
            render_chat()
        else:
            render_kb_management()
    elif st.session_state["authentication_status"] is False:
        st.error('用户名或密码不正确')
    elif st.session_state["authentication_status"] is None:
        st.warning('请输入用户名和密码')

if __name__ == "__main__":
    main()