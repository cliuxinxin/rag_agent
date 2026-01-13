# frontend/views/deep_mastery.py
import streamlit as st
import json
from langchain_core.messages import HumanMessage, AIMessage
from src.nodes.mastery_nodes import extractor_node, expander_node, chat_node
from src.db import create_mastery_session, get_mastery_session, update_mastery_concepts, get_all_mastery_sessions, update_mastery_session_data


def render():
    st.header("🎓 20/80 深度掌握引擎")
    st.caption("二八定律：掌握 20% 的底层逻辑，推导 80% 的应用特性。")
    
    # === 侧边栏逻辑修复 ===
    with st.sidebar:
        st.divider()
        st.subheader("📚 学习记录")
        
        # 1. 彻底重置按钮
        if st.button("➕ 开始新学习", use_container_width=True, type="primary"):
            st.session_state.mastery_state = None # 彻底清空
            st.rerun()
            
        sessions = get_all_mastery_sessions()
        for s in sessions:
            # 2. 历史记录恢复逻辑
            if st.button(f"📖 {s['topic']}", key=f"mast_{s['id']}"):
                concepts = s['concepts_data'] # DB层已经解析为List了
                
                # 从 concepts 列表中恢复缓存 (details_cache)
                restored_details = {}
                restored_chats = {}
                
                # 遍历列表，如果之前生成过 detail，就恢复到缓存字典里
                if isinstance(concepts, list):
                    for c in concepts:
                        if "detail" in c and c["detail"]:
                            if isinstance(c["detail"], dict):
                                # 如果已经是结构化数据
                                restored_details[c["name"]] = c["detail"]
                            else:
                                # 如果是旧格式字符串，尝试解析
                                try:
                                    parsed_detail = json.loads(c["detail"])
                                    restored_details[c["name"]] = parsed_detail
                                except:
                                    restored_details[c["name"]] = {"one_sentence_def": c["detail"], "analogy": "", "core_logic": c["detail"], "relationships": [], "derivations": [], "suggested_questions": []}
                            
                            restored_chats[c["name"]] = [AIMessage(content=f"已恢复【{c['name']}】的上下文。")]

                # 重建完整的 State
                st.session_state.mastery_state = {
                    "session_id": s['id'],
                    "topic": s['topic'],
                    "core_concepts": concepts if isinstance(concepts, list) else [],
                    "details_cache": restored_details,
                    "chat_histories_cache": restored_chats,
                    "selected_concept": None, # 切换 Session 时，不要默认选中任何东西，防止串台
                    "concept_detail": "",
                    "chat_history": [],
                    "current_suggestions": []
                }
                st.rerun()

    if "mastery_state" not in st.session_state or st.session_state.mastery_state is None:
        render_entry_page()
    else:
        render_dashboard()


def render_entry_page():
    """入口页：输入主题"""
    st.markdown("---")
    c1, c2 = st.columns([3, 1])
    with c1:
        # 使用 key 避免状态残留
        topic_input = st.text_input("你想深度掌握什么？", placeholder="例如：比特币、React框架...", key="new_topic_input")
    with c2:
        st.write("") 
        st.write("") 
        start_btn = st.button("🚀 降维打击", type="primary", use_container_width=True)

    if start_btn and topic_input:
        with st.status(f"🧠 正在解析【{topic_input}】的核心公理...", expanded=True):
            # 1. 创建 DB 记录
            sid = create_mastery_session(topic_input)
            
            # 2. 运行 LLM 提取
            # 确保传入的是当前的 topic_input
            result = extractor_node({"topic": topic_input})
            
            # 3. 构造全新的 State (防止继承旧数据)
            new_state = {
                "session_id": sid,
                "topic": topic_input,
                "core_concepts": result["core_concepts"],
                "details_cache": {},        
                "chat_histories_cache": {}, 
                "selected_concept": None,
                "current_suggestions": []
            }
            
            # 4. 存入 Session State
            st.session_state.mastery_state = new_state
            
            # 5. 存入 DB
            update_mastery_session_data(sid, result["core_concepts"])
            
            st.rerun()


def handle_user_input(state, concept, text):
    """处理用户输入（无论是打字还是点击按钮）"""
    # 1. 获取历史
    history = state["chat_histories_cache"].get(concept, [])
    
    # 2. 添加用户消息
    history.append(HumanMessage(content=text))
    
    # 3. 构造临时 state 调用 chat_node
    temp_state = {
        "topic": state["topic"],
        "selected_concept": concept,
        "chat_history": history
    }
    
    # 4. 调用 AI
    res = chat_node(temp_state)
    
    # 5. 更新缓存
    # chat_node 返回的是增量，这里我们取最后一条 AI 回复
    ai_msg = res["chat_history"][-1]
    history.append(ai_msg)
    
    state["chat_histories_cache"][concept] = history
    
    # 6. 持久化 (可选，建议做)
    # update_mastery_session_chat(state["session_id"], concept, history)


def render_dashboard():
    state = st.session_state.mastery_state
    session_id = state["session_id"]
    
    # 顶部标题栏
    st.markdown(f"### 🏷️ 主题：{state['topic']}")
    
    col_nav, col_main = st.columns([1, 3]) # 调整比例，让右侧宽一点
    
    # === 左侧导航 (逻辑微调) ===
    with col_nav:
        st.caption("核心节点导航")
        for idx, concept in enumerate(state["core_concepts"]):
            name = concept["name"]
            has_cache = name in state["details_cache"]
            
            # 选中状态样式
            is_selected = (state.get("selected_concept") == name)
            btn_type = "primary" if is_selected else "secondary"
            icon = "🟢" if has_cache else "⚪"
            
            if st.button(f"{name} {icon}", key=f"con_{idx}", type=btn_type, use_container_width=True):
                state["selected_concept"] = name
                
                # 如果没有缓存，或者缓存是旧格式（字符串），则重新生成
                cache_data = state["details_cache"].get(name)
                if not cache_data or isinstance(cache_data, str):
                    with st.spinner(f"正在解构 {name} 的底层逻辑..."):
                        res = expander_node(state)
                        # 存入结构化数据
                        state["details_cache"][name] = res["concept_detail_data"]
                        state["chat_histories_cache"][name] = [] # 清空聊天
                        
                        # 存入 DB (需要把 dict 转 json string 存，或者 DB 结构支持)
                        # 这里简化：我们假设 DB update 函数能处理 dict
                        state["core_concepts"][idx]["detail"] = res["concept_detail_data"]
                        update_mastery_session_data(session_id, state["core_concepts"])
                st.rerun()

    # === 右侧核心展示区 ===
    with col_main:
        selected = state.get("selected_concept")
        
        if not selected:
             st.info("👈 请点击左侧任一核心概念，开始深度学习。")
             return

        # 获取数据
        data = state["details_cache"].get(selected)
        if isinstance(data, str): # 兼容旧数据
            st.warning("旧数据格式，请重新生成。")
            return
            
        chat_history = state["chat_histories_cache"].get(selected, [])

        # --- 第一部分：知识仪表盘 (The Dashboard) ---
        with st.container(border=True):
            # 1. 标题与定义
            st.subheader(f"🧩 {selected}")
            st.info(f"💡 **本质定义**：{data.get('one_sentence_def', '暂无')}")
            
            # 2. 神类比 (高亮显示)
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <strong>🍎 神类比：</strong> {data.get('analogy', '暂无')}
            </div>
            """, unsafe_allow_html=True)
            
            # 3. 核心逻辑与关系 (Tab 分页)
            tab1, tab2, tab3 = st.tabs(["⚙️ 底层逻辑", "🤝 拓扑关系", "🌳 衍生特性 (80%)"])
            
            with tab1:
                st.write(data.get('core_logic', '暂无'))
            
            with tab2:
                for rel in data.get('relationships', []):
                    st.markdown(f"- {rel}")
                    
            with tab3:
                for der in data.get('derivations', []):
                    st.markdown(f"- {der}")

        # --- 第二部分：交互区 (Interaction) ---
        st.write("")
        st.subheader("💬 深度追问")
        
        # 1. 聊天记录展示
        if chat_history:
            for msg in chat_history:
                role = "user" if isinstance(msg, HumanMessage) else "assistant"
                with st.chat_message(role):
                    st.markdown(msg.content)
        else:
            st.caption("暂无对话，点击下方按钮快速提问 👇")

        # 2. 快捷提问按钮 (Chips)
        suggestions = data.get("suggested_questions", [])
        if suggestions:
            st.write("🤔 **猜你想问：**")
            cols = st.columns(min(len(suggestions), 3))  # 最多3列
            for i, q in enumerate(suggestions):
                if i < 3:  # 限制最多显示3个
                    if cols[i].button(q, key=f"sugg_{selected}_{i}", use_container_width=True):
                        handle_user_input(state, selected, q)
                        st.rerun()

        # 3. 输入框
        user_input = st.chat_input("输入你的问题...", key=f"chat_in_{selected}")
        if user_input:
            handle_user_input(state, selected, user_input)
            st.rerun()