import streamlit as st
import time
import json
from src.graphs.write_graph_v2 import planning_graph, drafting_graph
from src.db import create_writing_project, update_project_draft, update_project_outline


def render():
    st.header("📰 DeepSeek 新闻工作室 (Writing 2.0)")
    st.caption("Context Caching 驱动 | 采编室模式 | 事实核查 | 深度润色")

    if "newsroom_state" not in st.session_state:
        st.session_state.newsroom_state = None

    steps = ["1. 素材与定调", "2. 架构与大纲", "3. 采编与撰写", "4. 成稿"]
    current_step = 0
    if st.session_state.newsroom_state:
        s = st.session_state.newsroom_state
        if s.get("final_article"):
            current_step = 3
        elif s.get("outline"):
            current_step = 2
        elif s.get("generated_angles"):
            current_step = 1

    st.progress((current_step + 1) / 4, text=f"当前阶段: {steps[current_step]}")

    if current_step == 0:
        render_step_setup()
    elif current_step == 1:
        render_step_angle_selection()
    elif current_step == 2:
        render_step_execution()
    elif current_step == 3:
        render_step_final()


def render_step_setup():
    st.subheader("📁 第一步：导入素材")

    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("上传参考文档 (PDF/TXT)", type=["pdf", "txt"])
    with col2:
        text_input = st.text_area("或直接粘贴长文本", height=150)

    requirement = st.text_area(
        "写作需求/目标读者",
        placeholder="例：写一篇关于 DeepSeek 技术原理的深度分析，面向非技术人员，通俗易懂但有深度。",
        height=100,
    )

    if st.button("🚀 启动策划会", type="primary"):
        full_content = ""
        if uploaded_file:
            full_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        elif text_input:
            full_content = text_input

        if not full_content or not requirement:
            st.error("请提供内容和需求")
            return

        with st.spinner("首席策划正在分析文档..."):
            initial_state = {
                "full_content": full_content,
                "user_requirement": requirement,
                "generated_angles": [],
                "selected_angle": {},
                "outline": [],
                "section_drafts": [],
                "current_section_index": 0,
                "loop_count": 0,
            }

            for step in planning_graph.stream(initial_state):
                for node, update in step.items():
                    if "generated_angles" in update:
                        initial_state.update(update)

            st.session_state.newsroom_state = initial_state
            st.rerun()


def render_step_angle_selection():
    st.subheader("🎯 第二步：选题定调")
    state = st.session_state.newsroom_state
    angles = state.get("generated_angles", [])

    st.write("首席策划为您构思了以下 3 个切入角度，请选择一个：")

    cols = st.columns(3)
    for i, angle in enumerate(angles):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {angle['title']}")
                st.caption(angle['desc'])
                st.info(f"💡 {angle['reasoning']}")
                if st.button(f"选择此角度", key=f"angle_{i}", use_container_width=True):
                    state["selected_angle"] = angle
                    st.rerun()


def render_step_execution():
    st.subheader("🏗️ 第三步：架构与执行")
    state = st.session_state.newsroom_state

    if not state.get("outline"):
        with st.status("🏗️ 架构师正在绘制蓝图...", expanded=True) as status:
            from src.nodes.write_nodes_v2 import outline_architect_node

            update = outline_architect_node(state)
            state.update(update)
            status.update(label="大纲已生成！", state="complete")
            st.rerun()

    outline = state.get("outline", [])
    with st.expander("📝 查看/调整大纲", expanded=True):
        for i, sec in enumerate(outline):
            st.markdown(f"**{i+1}. {sec['title']}**")
            st.caption(f"主旨: {sec['gist']}")
            st.text(f"关键事实: {sec.get('key_facts', '无')}")
            st.divider()

    if st.button("✅ 确认大纲，开始采编与撰写", type="primary"):
        run_drafting_loop()


def run_drafting_loop():
    state = st.session_state.newsroom_state
    status_box = st.status("🚀 新闻工作室正在全速运转...", expanded=True)
    progress_bar = st.progress(0)

    draft_placeholder = st.empty()
    total_sections = len(state["outline"])

    try:
        for step in drafting_graph.stream(state):
            for node_name, update in step.items():
                state.update(update)

                if node_name == "Researcher":
                    sec_idx = state["current_section_index"]
                    title = state["outline"][sec_idx]["title"]
                    status_box.write(f"🕵️‍♂️ **内部探员**: 正在查证第 {sec_idx+1} 章【{title}】的素材...")
                elif node_name == "Drafter":
                    sec_idx = state["current_section_index"]
                    finished_title = state["outline"][sec_idx - 1]["title"]
                    status_box.write(f"✍️ **撰稿人**: 第 {sec_idx} 章【{finished_title}】草稿完成。")
                    progress_bar.progress(sec_idx / total_sections)

                    current_drafts = "\n\n".join(state["section_drafts"])
                    draft_placeholder.markdown(current_drafts + "\n\n*(正在撰写下一章...)*")
                elif node_name == "Reviewer":
                    status_box.write("🧐 **毒舌主编**: 正在审阅全稿，提出修改意见...")
                elif node_name == "Polisher":
                    status_box.write("✨ **润色师**: 正在根据意见进行最终打磨...")

        status_box.update(label="✅ 所有工作已完成！", state="complete", expanded=False)
        st.rerun()

    except Exception as e:
        st.error(f"运行出错: {e}")


def render_step_final():
    state = st.session_state.newsroom_state
    st.subheader("📰 最终成稿")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(state["final_article"])
        st.divider()
        if st.button("🔄 不满意？重新润色"):
            if "final_article" in state:
                del state["final_article"]
            st.rerun()

    with col2:
        st.info("💡 主编审阅意见")
        st.markdown(state.get("critique_notes", "无意见"))

        st.divider()
        st.success("🎉 稿件已就绪")
        if st.button("💾 归档到项目库"):
            try:
                outline_json = json.dumps(state["outline"], ensure_ascii=False)
                pid = create_writing_project(
                    title=state["selected_angle"].get("title", "未命名项目"),
                    requirements=state["user_requirement"],
                    source_type="newsroom_v2",
                    source_data=json.dumps(state["selected_angle"], ensure_ascii=False),
                )
                update_project_outline(pid, state["outline"], research_report=state.get("critique_notes", ""))
                update_project_draft(pid, state["final_article"])
                st.success(f"已保存！项目ID: {pid}")
            except Exception as e:
                st.error(f"保存失败: {e}")

    if st.button("🔙 开始新项目"):
        st.session_state.newsroom_state = None
        st.rerun()

