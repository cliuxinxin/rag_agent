import json
import os
import tempfile
import streamlit as st
import streamlit.components.v1 as comp
from langchain_community.document_loaders import PyPDFLoader
from src.graphs.write_graph_v2 import planning_graph, drafting_graph
from src.db import (
    create_writing_project,
    update_project_draft,
    update_project_outline,
    get_projects_by_source,
    get_writing_project,
    delete_project # [新增引用]
)

def load_file_content(uploaded_file) -> str:
    """
    统一的文件读取逻辑 (与 Deep Read 模块保持一致)
    支持 PDF 和 TXT 的文本提取
    """
    file_ext = uploaded_file.name.split(".")[-1].lower()
    full_text = ""
    
    # 创建临时文件以供 PyPDFLoader 读取
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
        
    try:
        if file_ext == "pdf":
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            full_text = "\n\n".join([p.page_content for p in pages])
        else:
            # 默认为文本文件
            with open(tmp_path, "r", encoding="utf-8") as f:
                full_text = f.read()
    except Exception as e:
        st.error(f"文件读取失败: {e}")
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return full_text

def render():
    # === [修改] 侧边栏结构优化 ===
    with st.sidebar:
        st.header("🗞️ 新闻工作室")
        
        # 1. 新建项目按钮 (全局重置)
        if st.button("➕ 开启新策划", type="primary", use_container_width=True):
            st.session_state.newsroom_state = None
            st.rerun()
            
        st.divider()
        st.subheader("📜 项目历史")
        render_history_sidebar()

    st.header("📰 DeepSeek 新闻工作室 (Writing 2.0)")
    st.caption("Context Caching 驱动 | 采编室模式 | 事实核查 | 深度润色")

    if "newsroom_state" not in st.session_state:
        st.session_state.newsroom_state = None

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
    
    # === [新增] 搜索开关 ===
    enable_search = st.checkbox(
        "🌍 开启联网事实核查 (Tavily Search)", 
        value=False,
        help="开启后，策划阶段将搜索行业背景，采编阶段将自动核实数据。请确保 .env 中配置了 TAVILY_API_KEY。"
    )

    if st.button("🚀 启动策划会", type="primary"):
        full_content = ""
        if uploaded_file:
            with st.spinner("正在提取文档内容..."):
                full_content = load_file_content(uploaded_file)
        elif text_input:
            full_content = text_input

        if not full_content or not requirement:
            st.error("请提供内容和需求")
            return

        if not full_content.strip():
            st.error("文档内容提取为空，请检查文件是否包含可复制的文本。")
            return

        # 长度保护（10 万字符）
        MAX_CHARS = 100000
        if len(full_content) > MAX_CHARS:
            st.warning(f"⚠️ 文档过长 ({len(full_content)} 字)，已截取前 {MAX_CHARS} 字。")
            full_content = full_content[:MAX_CHARS] + "\n...(内容已截断)..."

        with st.spinner("首席策划正在分析文档..."):
            initial_state = {
                "project_id": None,  # [新增] 初始化为 None
                "full_content": full_content,
                "user_requirement": requirement,
                "enable_web_search": enable_search, # <--- [新增] 存入初始状态
                "generated_angles": [],
                "selected_angle": {},
                "outline": [],
                "section_drafts": [],
                "current_section_index": 0,
                "loop_count": 0,
            }

            try:
                for step in planning_graph.stream(initial_state):
                    for node, update in step.items():
                        if "generated_angles" in update:
                            initial_state.update(update)
                st.session_state.newsroom_state = initial_state
                st.rerun()
            except Exception as e:
                st.error(f"分析失败，可能是内容过长或网络波动。错误信息: {e}")


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
        for step in drafting_graph.stream(state, config={"recursion_limit": 50}):
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
        if state.get("critique_notes"):
            with st.expander("🧐 查看主编审阅意见 (Reviewer Notes)", expanded=False):
                st.info(state["critique_notes"])

        st.markdown(state["final_article"])
        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            # 判断是否是已存在的项目
            is_existing = state.get("project_id") is not None
            btn_label = "💾 更新归档" if is_existing else "💾 新建归档"
            
            if st.button(btn_label, use_container_width=True, type="primary"):
                try:
                    if is_existing:
                        # 更新逻辑
                        pid = state["project_id"]
                        update_project_outline(pid, state["outline"], research_report=state.get("critique_notes", ""))
                        update_project_draft(pid, state["final_article"])
                        st.success(f"项目已更新！(ID: {pid})")
                    else:
                        # 新建逻辑
                        pid = create_writing_project(
                            title=state["selected_angle"].get("title", "未命名项目"),
                            requirements=state["user_requirement"],
                            source_type="newsroom_v2",
                            source_data=json.dumps(state["selected_angle"], ensure_ascii=False),
                        )
                        # 补全后续字段
                        update_project_outline(pid, state["outline"], research_report=state.get("critique_notes", ""))
                        update_project_draft(pid, state["final_article"])
                        
                        # 回写 ID 到状态，避免重复创建
                        state["project_id"] = pid
                        st.success(f"已新建归档！(ID: {pid})")
                        # 稍微延迟刷新以更新 Sidebar
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"保存失败: {e}")
        with col2:
            if st.button("🔄 重新润色", use_container_width=True):
                if "final_article" in state:
                    del state["final_article"]
                st.rerun()
        with col3:
            if st.button("🔙 退出/重置", use_container_width=True):
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


# 历史项目侧边栏
def render_history_sidebar():
    projects = get_projects_by_source("newsroom_v2")
    if not projects:
        st.caption("暂无历史项目。")
        return

    st.markdown("---")
    for p in projects:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                f"📄 {p['title']}",
                key=f"hist_{p['id']}",
                use_container_width=True,
                help=f"更新时间: {p['updated_at']}",
            ):
                data = get_writing_project(p["id"])
                if data:
                    st.session_state.newsroom_state = {
                        "project_id": p["id"],  # [新增] 回填 project_id
                        "full_content": "（从历史记录恢复，无原始内容）",
                        "user_requirement": data.get("requirements", ""),
                        "generated_angles": [],
                        "selected_angle": json.loads(data.get("source_data", "{}")),
                        "outline": data.get("outline_data", []),
                        "section_drafts": [],
                        "current_section_index": 999,
                        "loop_count": 0,
                        "final_article": data.get("full_draft", ""),
                        "critique_notes": data.get("research_report", ""),
                    }
                    st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{p['id']}", help="删除该项目"):
                delete_project(p["id"])
                st.rerun()


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

