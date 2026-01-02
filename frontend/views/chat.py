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
from src.logger import get_logger

logger = get_logger("View_Chat")

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
    """
    格式化显示消息：将正文直接显示，将引用/笔记放入折叠框
    """
    # 定义分隔符
    split_markers = ["【🕵️‍♂️ 调查笔记】", "【📚 原始片段】", "【原始知识库片段】", "<details>"]
    
    split_index = -1
    # 找到第一个出现的分隔符位置
    for marker in split_markers:
        idx = content.find(marker)
        if idx != -1:
            if split_index == -1 or idx < split_index:
                split_index = idx
    
    if split_index != -1:
        # 分割正文和附录
        main_text = content[:split_index].strip()
        references = content[split_index:].strip()
        
        # 1. 显示正文
        if main_text:
            st.markdown(main_text)
        else:
            # 极端情况：只有引用没有正文
            st.markdown("（基于以下参考资料生成）")

        # 2. 显示折叠的附录
        with st.expander("📚 查看引用与思考过程 (Reference & Logs)", expanded=False):
            st.markdown(references, unsafe_allow_html=True)
    else:
        # 没有分隔符，直接全部显示
        st.markdown(content)

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
        logger.info(f" >>> 收到用户输入: {final_query} <<<")
        
        if not st.session_state.selected_kbs:
            logger.warning("用户未选择知识库，操作中止")
            st.error("请选择知识库！")
            return
        
        with st.spinner("加载索引..."):
            try:
                source_documents, vector_store = load_kbs(st.session_state.selected_kbs)
                logger.info(f"知识库加载成功: {st.session_state.selected_kbs}")
            except Exception as e:
                logger.error(f"知识库加载失败: {e}", exc_info=True)
                st.error("知识库加载出错")
                return
        
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
            "kb_names": st.session_state.selected_kbs,  # [新增] 传递知识库名称列表
            "next": "Supervisor",
            "current_search_query": "",
            "final_evidence": [],
            "loop_count": 0,
            "attempted_searches": [],
            "research_notes": [],
            "failed_topics": [],
            # [新增] 初始化为空或通用描述
            "kb_summary": "暂时未知（等待检索后分析）",
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
                logger.info("开始执行 Graph Stream...")
                graph_config = {"recursion_limit": 50}
                for step in graph.stream(initial_state, config=graph_config):
                    for node_name, update in step.items():
                        # [Log] 记录流式步骤
                        logger.debug(f"Graph 更新 - 节点: {node_name}")
                        
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
                                logger.info("获得 Answerer 最终回复")
                
                status_container.update(label="回答完成", state="complete", expanded=False)
                
                if final_answer:
                    # 1. 先保存到 State 和 DB
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})
                    if st.session_state.current_session_id:
                        add_message(st.session_state.current_session_id, "assistant", final_answer)
                    
                    # 2. 【关键修改】立即渲染当前回答！确保用户先看到结果
                    format_display_message(final_answer)
                    
                    # 3. 最后处理智能标题和刷新 (仅在第一轮对话后)
                    if st.session_state.current_session_id and len(st.session_state.messages) == 2:
                        # 可以在这里加个 toast 提示，优化体验
                        st.toast("正在生成会话标题...")
                        smart_title = generate_smart_title(final_query, final_answer)
                        update_session_title(st.session_state.current_session_id, smart_title)
                        st.rerun()  # 此时再刷新，内容已经显示过了，刷新后也会从 History 再次加载
                else:
                    logger.warning("Graph 执行完成但没有生成 final_answer")
            
            except Exception as e:
                status_container.update(label="Error", state="error")
                logger.error(f"Graph 运行过程中发生崩溃: {e}", exc_info=True)
                st.error(f"运行错误: {e}")