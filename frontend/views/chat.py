# frontend/views/chat.py
import streamlit as st

# === 修改开始 ===
# [删除] from src.graph import graph
# [新增] 引用新的 chat_graph，并重命名为 graph 以兼容下方代码
from src.graphs.chat_graph import chat_graph as graph 
# === 修改结束 ===

from src.utils import load_file, split_documents
from src.storage import load_kbs, list_kbs # 补全 list_kbs
from src.db import init_db, create_session, get_all_sessions, get_messages, add_message, delete_session, update_session_title
from src.nodes.common import get_llm # 确保引用路径正确
from langchain_core.messages import HumanMessage, SystemMessage # 补全 SystemMessage
# === [修改] 适配 Langfuse v3 ===
try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:
    LangfuseCallbackHandler = None

# 初始化数据库
init_db()

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
    # ... (此处省略具体实现，保持与原文件一致)

def render():
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
                # === [修改] 配置 Graph 运行时参数 ===
                graph_config = {"recursion_limit": 50}
                
                # 只有当模块加载成功且有 session_id 时才配置
                if LangfuseCallbackHandler and st.session_state.current_session_id:
                    # 1. 初始化 Handler (无参数)
                    session_handler = LangfuseCallbackHandler()
                    
                    # 2. 注入 callbacks
                    graph_config["callbacks"] = [session_handler]
                    
                    # 3. [v3 重点] 通过 metadata 传递 session_id
                    graph_config["metadata"] = {
                        "langfuse_session_id": st.session_state.current_session_id,
                        "langfuse_user_id": "user_admin" 
                    }
                
                # 3. 传入 config
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