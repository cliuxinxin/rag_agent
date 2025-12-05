import json
import streamlit as st
import streamlit.components.v1 as comp
from src.graphs.write_graph_v2 import planning_graph, drafting_graph
from src.db import (
    create_writing_project,
    update_project_draft,
    update_project_outline,
    get_projects_by_source,
    get_writing_project,
)


def render():
    st.header("📰 DeepSeek 新闻工作室 (Writing 2.0)")
    st.caption("Context Caching 驱动 | 采编室模式 | 事实核查 | 深度润色")

    if "newsroom_state" not in st.session_state:
        st.session_state.newsroom_state = None

    render_history_panel()

    steps = ["1. 素材与定调", "2. 架构与大纲", "3. 采编与撰写", "4. 成稿与发行"]
    current_step = 0
    if st.session_state.newsroom_state:
        s = st.session_state.newsroom_state
        if s.get("final_article"):
            current_step = 3
        elif s.get("outline"):
            current_step = 2
        elif s.get("selected_angle"):
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

    tab_text, tab_card = st.tabs(["📄 文字稿件", "🖼️ 生成知识卡片"])

    with tab_text:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(state["final_article"])
        with col2:
            st.info("💡 主编审阅意见")
            st.markdown(state.get("critique_notes", "无意见"))
            st.divider()
            if st.button("💾 归档到项目库", use_container_width=True):
                try:
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

            if st.button("🔄 重新润色", use_container_width=True):
                if "final_article" in state:
                    del state["final_article"]
                st.rerun()

            st.markdown("---")
            if st.button("🔙 开始新项目", use_container_width=True):
                st.session_state.newsroom_state = None
                st.rerun()

    with tab_card:
        st.markdown("##### 📸 知识卡片预览")
        st.caption("基于 HTML5 渲染，支持高清中文下载。")
        render_html_card(
            title=state["selected_angle"].get("title", "新闻工作室稿件"),
            content_md=state["final_article"],
            source_tag="DeepSeek Newsroom",
        )


# === 历史项目查看 ===
def render_history_panel():
    with st.expander("📜 查看历史项目（Newsroom）", expanded=False):
        projects = get_projects_by_source("newsroom_v2")
        if not projects:
            st.info("暂无历史项目。")
            return
        options = {f"{p['title']} ({p['updated_at'][:10]})": p["id"] for p in projects}
        selected = st.selectbox("选择项目查看", list(options.keys()))
        project_id = options[selected]
        data = get_writing_project(project_id)
        if not data:
            st.error("项目数据不存在或已删除")
            return

        st.markdown(f"### {data['title']}")
        st.caption(f"需求：{data.get('requirements','')}")
        st.divider()
        st.markdown("#### 成稿内容")
        st.markdown(data.get("full_draft", "无成稿"))

        st.divider()
        st.markdown("#### 📸 知识卡片")
        if data.get("full_draft"):
            render_html_card(
                title=data["title"],
                content_md=data["full_draft"],
                source_tag="DeepSeek Newsroom Archive",
            )


def render_html_card(title, content_md, source_tag):
    """基于 HTML+html2canvas 生成知识卡片，避免中文乱码"""
    import markdown
    import re

    html_content = markdown.markdown(content_md)
    clean_title = re.sub(r"[^\w\s-]", "", title).strip() or "newsroom_card"

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&display=swap');
            body {{
                background-color: #f0f2f6;
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
            }}
            #card-container {{
                width: 450px;
                background: white;
                box-shadow: 0 10px 30px rgba(0,0,0,0.15);
                overflow: hidden;
                position: relative;
            }}
            .card-header {{
                background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%);
                color: white;
                padding: 40px 30px;
                position: relative;
            }}
            .card-tag {{
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 2px;
                opacity: 0.8;
                margin-bottom: 10px;
                border: 1px solid rgba(255,255,255,0.4);
                display: inline-block;
                padding: 2px 8px;
                border-radius: 20px;
            }}
            .card-title {{
                font-family: 'Noto Serif SC', "Microsoft YaHei", serif;
                font-size: 26px;
                font-weight: 700;
                line-height: 1.4;
                margin: 0;
                text-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            .card-body {{
                padding: 30px;
                color: #333;
                font-size: 14px;
                line-height: 1.8;
                text-align: justify;
                background-image: radial-gradient(#e6e6e6 1px, transparent 1px);
                background-size: 20px 20px;
                background-color: #fff;
            }}
            .card-body h1, .card-body h2 {{
                font-size: 18px;
                color: #2c3e50;
                margin-top: 20px;
                margin-bottom: 10px;
                border-left: 4px solid #4ca1af;
                padding-left: 10px;
            }}
            .card-body h3 {{ font-size: 16px; color: #444; margin-top: 15px; }}
            .card-body p {{ margin-bottom: 15px; }}
            .card-body strong {{ color: #000; font-weight: 700; }}
            .card-body ul {{ padding-left: 20px; margin-bottom: 15px; }}
            .card-body li {{ margin-bottom: 5px; }}
            .card-footer {{
                background: #f8f9fa;
                padding: 15px 30px;
                text-align: center;
                font-size: 12px;
                color: #888;
                border-top: 1px dashed #ddd;
            }}
            .dl-btn {{
                margin-top: 20px;
                padding: 12px 24px;
                background: #ff4b4b;
                color: white;
                border: none;
                border-radius: 50px;
                font-size: 14px;
                font-weight: bold;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3);
                transition: transform 0.1s;
                font-family: "Microsoft YaHei", sans-serif;
            }}
            .dl-btn:active {{ transform: scale(0.95); }}
            .dl-btn:hover {{ background: #ff3333; }}
        </style>
    </head>
    <body>
        <div id="card-container">
            <div class="card-header">
                <div class="card-tag">{source_tag}</div>
                <div class="card-title">{title}</div>
            </div>
            <div class="card-body">
                {html_content}
            </div>
            <div class="card-footer">
                Powered by DeepSeek RAG Pro
            </div>
        </div>
        <button class="dl-btn" onclick="downloadCard()">📸 保存为图片</button>
        <script>
            function downloadCard() {{
                const node = document.getElementById('card-container');
                const btn = document.querySelector('.dl-btn');
                btn.innerText = "⏳ 生成中...";
                html2canvas(node, {{
                    scale: 2,
                    useCORS: true,
                    backgroundColor: "#ffffff",
                    scrollY: 0
                }}).then(canvas => {{
                    const link = document.createElement('a');
                    link.download = '{clean_title}_知识卡片.png';
                    link.href = canvas.toDataURL("image/png");
                    link.click();
                    btn.innerText = "📸 保存为图片";
                }});
            }}
        </script>
    </body>
    </html>
    """

    comp.html(html_template, height=800, scrolling=True)

