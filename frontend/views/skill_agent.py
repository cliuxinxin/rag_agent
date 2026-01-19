# frontend/views/skill_agent.py
import streamlit as st
import re
import uuid
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.graphs.skill_graph import skill_graph
from src.skills.loader import SkillRegistry

# 你的项目风格
SKILLS_DIR = Path("skills")
registry = SkillRegistry()

def display_images_from_text(text_content):
    """从文本中检测图片文件名并在本地查找显示"""
    if not text_content: return
    # 匹配 .png, .jpg, .jpeg 结尾的文件名
    pattern = r"([a-zA-Z0-9_\-\.]+\.(?:png|jpg|jpeg))"
    matches = list(set(re.findall(pattern, text_content)))
    for filename in matches:
        # 在 skills 目录下递归查找
        found_files = list(SKILLS_DIR.rglob(filename))
        if found_files:
            # 使用 container 保证格式整齐
            with st.container():
                st.image(str(found_files[0]), caption=f"📊 {filename}", width=600)

def render():
    st.header("🤖 Skill Agent (工具智能体)")
    st.caption("基于路由器的多技能自治 Agent，支持 Python 脚本执行、图表绘制等。")

    # === 侧边栏技能展示 ===
    with st.sidebar:
        st.divider()
        st.subheader("🧩 可用技能")
        registry.refresh()
        skills = registry.list_skills()
        if not skills:
            st.info("暂无技能，请检查 skills 目录")
        for sk in skills:
            with st.expander(f"📦 {sk['name']}"):
                st.caption(sk.get('description', '无描述'))
                st.text(f"Ver: {sk.get('version')}")

        # 清除记忆按钮
        if st.button("🗑️ 清除当前对话记忆", use_container_width=True):
            st.session_state.skill_thread_id = str(uuid.uuid4()) # 生成新 ID 即等同于清空
            st.rerun()

    # === Session 初始化 ===
    if "skill_thread_id" not in st.session_state or not st.session_state.skill_thread_id:
        st.session_state.skill_thread_id = str(uuid.uuid4())

    thread_id = st.session_state.skill_thread_id
    config = {"configurable": {"thread_id": thread_id, "recursion_limit": 50}}

    # === 消息历史获取 ===
    try:
        curr_state = skill_graph.get_state(config)
        messages = curr_state.values.get("messages", []) if curr_state.values else []
    except Exception as e:
        messages = []
        # st.error(f"State load error: {e}")

    # === 欢迎语 ===
    if not messages:
        st.info("👋 你好，我是 Skill Agent。我可以运行 Python 脚本、查天气、画图等。请告诉我你需要什么。")

    # ==================================================================
    # 🔥 核心渲染逻辑优化：按"用户-AI"轮次分组
    # ==================================================================
    i = 0
    while i < len(messages):
        msg = messages[i]
        
        # 1. 遇到用户消息：渲染为 User Bubble
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.write(msg.content)
            i += 1
            
            # 2. 收集紧随其后的 AI 消息（直到下一条 HumanMessage 或结束）
            ai_turn_buffer = []
            while i < len(messages) and not isinstance(messages[i], HumanMessage):
                ai_turn_buffer.append(messages[i])
                i += 1
            
            # 3. 渲染这一轮的 AI 回复
            if ai_turn_buffer:
                with st.chat_message("assistant"):
                    # 3.1 寻找"最终回答"：通常是最后一条有文本内容的 AIMessage（且不是纯工具调用）
                    final_content = ""
                    # 倒序查找，找到最后一条有意义的回复
                    for m in reversed(ai_turn_buffer):
                        if isinstance(m, AIMessage) and m.content and not m.tool_calls:
                            final_content = m.content
                            break
                    
                    # 3.2 提取"中间过程"：除了最终回答之外的所有消息
                    intermediate_steps = []
                    # 简单的去重策略：如果 buffer 里最后一条就是 final_content，那它就不算中间步骤
                    # 但更稳妥的是遍历 buffer
                    found_final = False
                    for m in reversed(ai_turn_buffer):
                        if not found_final and isinstance(m, AIMessage) and m.content == final_content:
                            found_final = True
                            continue # 跳过作为"最终展示"的那条
                        intermediate_steps.insert(0, m) # 插入到前面，保持顺序
                    
                    # 3.3 渲染"思考过程"折叠框
                    # 如果有中间步骤（工具调用、工具回传、中间的思考念叨），则显示折叠框
                    if intermediate_steps:
                        # 计算步骤数（ToolMessage 的数量）
                        step_count = len([m for m in intermediate_steps if isinstance(m, ToolMessage)])
                        expander_label = f"⚙️ 思考与执行过程 ({step_count} 步)" if step_count > 0 else "🧠 思考过程"
                        
                        with st.expander(expander_label, expanded=False):
                            for step_msg in intermediate_steps:
                                if isinstance(step_msg, AIMessage):
                                    if step_msg.tool_calls:
                                        for tool in step_msg.tool_calls:
                                            st.markdown(f"**🛠️ 调用工具**: `{tool['name']}`")
                                            # st.json(tool['args']) # 参数太长可以不显示
                                    elif step_msg.content:
                                        st.markdown(f"**🤔 想法**: {step_msg.content}")
                                elif isinstance(step_msg, ToolMessage):
                                    st.markdown(f"**✅ 工具结果**: `{step_msg.name}`")
                                    st.code(step_msg.content[:500] + ("..." if len(step_msg.content) > 500 else ""))

                    # 3.4 渲染"最终回答"
                    if final_content:
                        st.markdown(final_content)
                        # 检查是否有图片需要渲染
                        display_images_from_text(final_content)
                    elif not intermediate_steps:
                        # 极端情况：既没中间步骤也没最终回答（可能是空消息）
                        st.caption("...")

    # ==================================================================
    # 输入与流式处理
    # ==================================================================
    if user_input := st.chat_input("输入指令..."):
        # 1. 显示用户输入
        with st.chat_message("user"):
            st.write(user_input)
        
        # 2. 运行 Graph
        with st.chat_message("assistant"):
            # 使用 status 容器来展示实时的流式动态（给用户一种正在工作的反馈）
            status_box = st.status("🧠 正在思考与调用工具...", expanded=True)
            response_placeholder = st.empty()
            
            try:
                inputs = {"messages": [HumanMessage(content=user_input)]}
                final_res = ""
                
                # Stream 模式
                for event in skill_graph.stream(inputs, config=config):
                    # 2.1 路由事件
                    if "router" in event:
                        r = event["router"]
                        skill = r.get("active_skill")
                        status_box.write(f"🚦 路由决策: {skill if skill else 'Default'}")
                    
                    # 2.2 工具执行事件
                    if "tools" in event:
                        # 这里的 event["tools"]["messages"] 是工具执行完后的 output 列表
                        for tool_msg in event["tools"]["messages"]:
                            status_box.write(f"✅ 工具完成: {tool_msg.name}")
                            # 可以在这里打印简短的日志
                            # status_box.code(tool_msg.content[:100])
                    
                    # 2.3 Agent 回复事件
                    if "agent" in event:
                        msgs = event["agent"]["messages"]
                        if msgs:
                            last_msg = msgs[-1]
                            # 如果有 content，说明是回复；如果有 tool_calls，说明是发起调用
                            if last_msg.content:
                                final_res = last_msg.content
                                response_placeholder.markdown(final_res)
                            if last_msg.tool_calls:
                                for t in last_msg.tool_calls:
                                    status_box.write(f"🛠️ 请求工具: {t['name']}")

                # 完成后，收起状态栏
                status_box.update(label="执行完成", state="complete", expanded=False)
                
                # 再次刷新最终结果（确保 markdown 渲染正确）
                if final_res:
                    response_placeholder.markdown(final_res)
                    display_images_from_text(final_res)
                    
            except Exception as e:
                status_box.update(label="发生错误", state="error")
                st.error(f"System Error: {e}")