# ./frontend/app.py
import sys
import os
import re
import html
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

# 添加 src 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import graph
from src.utils import load_file, split_documents
from src.storage import save_kb, load_kbs, list_kbs, delete_kb, get_kb_details

load_dotenv()
st.set_page_config(page_title="DeepSeek RAG Pro", layout="wide")

# === 全局 CSS 样式: 悬浮提示 + 锚点样式 ===
st.markdown("""
<style>
    /* 引用数字的基本样式 */
    .ref-link {
        color: #1f77b4;
        font-weight: bold;
        cursor: help;
        text-decoration: none;
        border-bottom: 1px dashed #1f77b4;
        margin: 0 2px;
        position: relative;
        display: inline-block;
    }
    
    /* 悬浮提示框 */
    .ref-link .ref-tooltip {
        visibility: hidden;
        width: 350px;
        background-color: #fff;
        color: #333;
        text-align: left;
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 6px;
        
        /* 定位 */
        position: absolute;
        z-index: 999999;
        bottom: 140%; /* 移高一点，防止遮挡 */
        left: 50%;
        transform: translateX(-50%);
        
        /* 视觉 */
        box-shadow: 0px 4px 15px rgba(0,0,0,0.2);
        opacity: 0;
        transition: opacity 0.2s;
        font-size: 13px;
        font-weight: normal;
        line-height: 1.5;
        white-space: normal;
        pointer-events: none; /* 鼠标穿透，防止闪烁 */
    }

    /* 鼠标悬停显示 */
    .ref-link:hover .ref-tooltip {
        visibility: visible;
        opacity: 1;
    }
    
    /* 提示框底部小三角 */
    .ref-link .ref-tooltip::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: #fff transparent transparent transparent;
    }
    
    /* 底部引用列表的目标高亮 */
    .ref-target {
        scroll-margin-top: 100px; /* 防止跳转后被顶部Header遮挡 */
        font-weight: bold;
        color: #e65100;
    }
</style>
""", unsafe_allow_html=True)

# === 初始化 Session State ===
for key in ["messages", "selected_kbs", "next_query", "attempted_searches", "research_notes", "failed_topics"]:
    if key not in st.session_state:
        if key == "messages": st.session_state[key] = []
        elif key == "next_query": st.session_state[key] = ""
        else: st.session_state[key] = []

def format_display_message(content):
    """
    解析 Answerer 的回复：
    1. 提取底部的 Raw Evidence。
    2. 将正文中的 [Ref 2, 5, 6] 替换为带有悬浮提示的 HTML。
    """
    # 1. 切分正文和附录
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

    # 2. 解析引用内容 (构建 ref_map)
    ref_map = {}
    if ref_text:
        # 匹配模式： > [Ref 1] 内容... 或 [Ref 1] 内容...
        # 兼容换行符
        # pattern: (行首或>)\s*\[Ref\s*(\d+)\]\s*(内容...)
        pattern = r"(?:>|\n|^)\s*\[Ref\s*(\d+)\]\s*(.*?)(?=\n\s*(?:>|\[Ref)|\Z)"
        matches = re.findall(pattern, ref_text, re.DOTALL)
        
        for ref_id, ref_content in matches:
            # 清洗内容
            clean_c = ref_content.strip().replace('"', "'")[:400] # 限制长度
            if len(ref_content) > 400: clean_c += "..."
            ref_map[ref_id] = clean_c

    # 3. 替换正文引用 (支持多引用 [Ref 1, 2])
    def replace_multi_ref(match):
        # 获取括号内的内容，如 "2, 5, 6"
        numbers_str = match.group(1)
        # 拆分数字
        numbers = [n.strip() for n in numbers_str.split(',') if n.strip()]
        
        html_parts = []
        for num in numbers:
            tooltip = ref_map.get(num, "未找到该引用的详细内容，请查看底部折叠区域。")
            # 构造单个数字的 HTML
            # href="#ref-{num}" 是尝试做页内跳转
            span = f'''
            <a href="#ref-{num}" class="ref-link">
                {num}
                <span class="ref-tooltip">
                    <strong>[Ref {num}]</strong><br/>
                    {html.escape(tooltip)}
                </span>
            </a>
            '''
            html_parts.append(span.strip())
        
        # 用逗号连接多个 span
        combined = ", ".join(html_parts)
        return f" [Ref {combined}] "

    # 正则：匹配 [Ref 1] 或 [Ref 1, 2, 3]
    # \[Ref\s+ 匹配开头
    # ([\d,\s]+) 捕获中间的数字和逗号
    # \] 匹配结尾
    enhanced_main_text = re.sub(r"\[Ref\s+([\d,\s]+)\]", replace_multi_ref, main_text)

    # 4. 处理底部的引用文本，增加锚点 id
    # 将 > [Ref 1] 替换为 > <span id="ref-1">[Ref 1]</span>
    if ref_text:
        def add_anchor(match):
            rid = match.group(1)
            return f'> <span id="ref-{rid}" class="ref-target">[Ref {rid}]</span>'
        
        # 简单的替换，给底部列表加 id
        enhanced_ref_text = re.sub(r">\s*\[Ref\s*(\d+)\]", add_anchor, ref_text)
    else:
        enhanced_ref_text = ""

    # === 渲染 ===
    st.markdown(enhanced_main_text, unsafe_allow_html=True)
    
    if enhanced_ref_text:
        with st.expander("📚 查看调查笔记与原始引用 (点击展开)", expanded=False):
            st.markdown(enhanced_ref_text, unsafe_allow_html=True)

    # === 4. 渲染建议按钮 (正则大升级) ===
    
    # 尝试匹配多种格式：
    # 1. 1. [点击] xxx
    # 2. [点击] xxx
    # 3. 1. xxx?
    # 4. 纯文本行 (针对 "建议进一步挖掘的问题" 下方的非空行)
    
    suggestions = []
    
    # 策略 A: 显式标记匹配
    s1 = re.findall(r"(?:\[点击\]|\[Click\])\s*(.*)", content)
    if s1: 
        suggestions = s1
    
    # 策略 B: 序号 + 问号匹配 (你的日志里是这种: "LAMP模块贡献度：...？")
    if not suggestions:
        # 匹配以 ? 结尾的行，或者包含中文问号的行
        # 排除掉太短的行（防止匹配到标题）
        s2 = re.findall(r"(?:^|\n)(?:[\d\.\-]*\s*)?(.{5,}?[?？])(?=\n|$)", content)
        if s2:
            suggestions = s2
            
    # 策略 C: 兜底匹配 (如果上方有 "建议进一步...问题" 标题，则提取其后的行)
    if not suggestions:
        # 找到标题位置
        header_match = re.search(r"(?:建议|后续).*?(?:问题|研究)", content)
        if header_match:
            # 提取标题之后的所有文本
            tail_text = content[header_match.end():]
            # 按行分割，过滤空行
            lines = [line.strip() for line in tail_text.split('\n') if line.strip()]
            # 取前3个非空行作为建议
            suggestions = lines[:3]

    # 渲染
    if suggestions:
        st.markdown("---")
        st.caption("👉 **您可以点击以下问题继续追问：**")
        cols = st.columns(len(suggestions))
        for idx, question in enumerate(suggestions):
            # 限制按钮文本长度，防止太长撑坏布局
            btn_label = question
            if len(btn_label) > 20: 
                btn_label = btn_label[:20] + "..."
                
            # 使用 help 显示完整问题
            if cols[idx].button(btn_label, help=question, key=f"sugg_{hash(content)}_{idx}"):
                st.session_state.next_query = question
                st.rerun()

def render_kb_management():
    st.header("📂 知识库管理")
    tabs = st.tabs(["📚 知识库列表 & 检视", "➕ 新建/追加知识"])
    
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