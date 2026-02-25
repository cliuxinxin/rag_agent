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
# [新增/移动] 将此行移到顶部，以便在 render_step_setup 中使用
from src.nodes.write_nodes_v2 import outline_architect_node, outline_refiner_node

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
    st.subheader("📁 第一步：导入素材与配置")

    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("上传参考文档 (PDF/TXT)", type=["pdf", "txt"])
    with col2:
        text_input = st.text_area("或直接粘贴长文本", height=150)

    st.markdown("---")
    st.write("⚙️ **写作配置**")
    
    # === [新增] 结构化配置区 ===
    c1, c2 = st.columns(2)
    with c1:
        style_tone = st.selectbox(
            "🎭 身份与语调",
            ["犀利独到 (资深主编)","客观中立 (分析师)", "深度专业 (技术专家)",  "通俗易懂 (科普博主)", "正式公文 (报告风格)"],
            index=0
        )
    with c2:
        length_opt = st.select_slider(
            "📏 预估篇幅",
            options=["短讯 (500字)", "标准 (1500字)", "深度长文 (3000字+)", "超长调研 (5000字+)"],
            value="标准 (1500字)"
        )
    
    must_haves = st.text_area(
        "📝 核心指令 / 必须包含的要素",
        placeholder="例：必须包含与 OpenAI 的参数对比；重点强调成本优势；语气要充满信心...",
        height=100
    )

    enable_search = st.checkbox(
        "🌍 开启联网事实核查 (Tavily Search)", 
        value=False,
        help="开启后，策划阶段将搜索行业背景，采编阶段将自动核实数据。"
    )

    # === [修改 1] 添加一键成文开关 ===
    auto_mode = st.checkbox(
        "⚡ 一键成文 (自动选角度2 + 自动写作)",
        value=False,
        help="选中后，将自动选择第二个切入角度，跳过大纲确认，直接生成最终文章。"
    )

    if st.button("🚀 启动策划会", type="primary"):
        full_content = ""
        if uploaded_file:
            with st.spinner("正在提取文档内容..."):
                full_content = load_file_content(uploaded_file)
        elif text_input:
            full_content = text_input

        if not full_content or not must_haves:
            st.error("请提供内容和核心指令")
            return

        if not full_content.strip():
            st.error("文档内容提取为空，请检查文件是否包含可复制的文本。")
            return

        # 长度保护（15 万字符）
        MAX_CHARS = 150000
        if len(full_content) > MAX_CHARS:
            st.warning(f"⚠️ 文档过长 ({len(full_content)} 字)，已截取前 {MAX_CHARS} 字。")
            full_content = full_content[:MAX_CHARS] + "\n...(内容已截断)..."

        # [修改] 使用 status 容器来显示过程
        with st.status("🚀 首席策划正在工作中...", expanded=True) as status_box:
            # === [修改] 初始状态构造 ===
            initial_state = {
                "project_id": None,
                "full_content": full_content,
                # 为了兼容性，我们将结构化数据拼接到 user_requirement，但也单独存
                "user_requirement": must_haves, 
                "style_tone": style_tone,    # 新增
                "article_length": length_opt, # 新增
                "must_haves": must_haves,    # 新增
                "enable_web_search": enable_search,
                "generated_angles": [],
                "macro_search_context": "", # 初始化
                # === [修改 2] 初始状态构造增加 auto_mode ===
                "auto_mode": auto_mode, # [新增] 保存开关状态
                "run_logs": [] # 初始化
            }

            try:
                # [关键修改] 使用 .stream() 而不是 hidden loop
                for step in planning_graph.stream(initial_state):
                    for node_name, update in step.items():
                        # 更新状态
                        initial_state.update(update)
                        
                        # [新增] 实时显示日志
                        if "run_logs" in update:
                            for log in update["run_logs"]:
                                status_box.write(log)
                        
                        # 显示节点进度
                        if node_name == "MacroSearch":
                            status_box.write("✅ 背景调查完成，正在构思角度...")
                        elif node_name == "AngleGen":
                            status_box.write("✅ 角度构思完成，正在生成大纲...")

                # === [修改 3] 核心逻辑分支 ===
                
                # 情况 A: 开启了一键成文
                if initial_state.get("auto_mode"):
                    status_box.write("⚡ **一键成文模式启动**：正在自动选择角度...")
                    
                    # 1. 自动选择角度 (默认选第2个，索引为1；如果不够则选第1个)
                    angles = initial_state.get("generated_angles", [])
                    if angles:
                        selected_idx = 1 if len(angles) > 1 else 0
                        initial_state["selected_angle"] = angles[selected_idx]
                        status_box.write(f"✅ 已选择角度：{angles[selected_idx]['title']}")
                    
                    # 2. 自动生成大纲 (手动调用节点逻辑)
                    status_box.write("🏗️ 正在跳过交互，直接构建大纲...")
                    outline_update = outline_architect_node(initial_state)
                    initial_state.update(outline_update)
                    
                    # 3. 更新 Session State 以便后续函数读取
                    st.session_state.newsroom_state = initial_state
                    
                    # 4. 直接调用写作循环 (Drafting Loop)
                    # 注意：run_drafting_loop 会创建它自己的 status 容器，这没问题，会堆叠显示
                    status_box.update(label="策划完成，进入自动写作...", state="complete", expanded=False)
                    run_drafting_loop() 
                    
                    # 5. 写作完成后刷新页面，展示最终结果
                    st.rerun()

                # 情况 B: 普通模式 (原有逻辑)
                else:
                    status_box.update(label="策划完成！", state="complete", expanded=False)
                    st.session_state.newsroom_state = initial_state
                    st.rerun()
                
            except Exception as e:
                st.error(f"出错: {e}")


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
    st.subheader("🏗️ 第三步：架构与大纲修订")
    state = st.session_state.newsroom_state

    # 1. 如果没有大纲，先生成大纲 (原有逻辑)
    if not state.get("outline"):
        with st.status("🏗️ 架构师正在绘制蓝图...", expanded=True) as status:
            update = outline_architect_node(state)
            state.update(update)
            status.update(label="初版大纲已生成！", state="complete")
            st.rerun()

    # 2. [新增] 大纲交互区 (谈判桌)
    st.info("💡 请检查下方大纲。如果不满意，可在下方直接输入修改意见，AI 将自动调整结构。")
    
    # 显示大纲卡片
    outline = state.get("outline", [])
    with st.container(border=True):
        st.markdown(f"### 📑 大纲预览 (v{state.get('loop_count', 0) + 1})")
        for i, sec in enumerate(outline):
            st.markdown(f"**{i+1}. {sec['title']}**")
            st.caption(f"主旨: {sec['gist']}")
            # st.text(f"关键事实: {sec.get('key_facts', '无')}") # 可以稍微折叠一下细节以免太长
    
    # 3. [新增] 修改意见输入框
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        user_feedback = st.text_input("💬 给架构师的修改指令", placeholder="例：删掉第3章；在第1章后增加‘市场背景’；把结尾改得更激昂一点...")
    with col_btn:
        refine_btn = st.button("🔄 执行修改")
        
    if refine_btn and user_feedback:
        with st.spinner("架构师正在调整图纸..."):
            # 手动调用 Refiner Node
            state["user_feedback_on_outline"] = user_feedback
            update = outline_refiner_node(state)
            state.update(update) # 更新大纲
            state["loop_count"] = state.get("loop_count", 0) + 1 # 记录版本
            st.success("大纲已更新！")
            st.rerun()

    st.divider()

    # 4. 确认定稿按钮
    st.write("👇 确认大纲无误后，点击下方按钮开始写作")
    if st.button("✅ 锁定大纲，开始采编与撰写", type="primary", use_container_width=True):
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
                
                # [新增] 优先显示日志 (搜索过程)
                if "run_logs" in update:
                    for log in update["run_logs"]:
                        status_box.write(log) # 直接打印搜索动作

                if node_name == "Researcher":
                    # ... (原有提示代码)
                    # status_box.write(...) # 可以保留或简化，因为上面已经打印了具体 log
                    pass 
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

        # === [新增] 自动归档逻辑 ===
        if state.get("auto_mode"):
            status_box.write("💾 **自动归档**: 正在保存项目到数据库...")
            try:
                # 1. 创建新项目
                pid = create_writing_project(
                    title=state["selected_angle"].get("title", "未命名项目"),
                    requirements=state["user_requirement"],
                    source_type="newsroom_v2",
                    source_data=json.dumps(state["selected_angle"], ensure_ascii=False),
                )
                # 2. 保存大纲和草稿
                update_project_outline(pid, state["outline"], research_report=state.get("critique_notes", ""))
                update_project_draft(pid, state.get("final_article", ""))
                
                # 3. 回写 ID
                state["project_id"] = pid
                status_box.write(f"✅ 项目已自动归档 (ID: {pid})")
            except Exception as save_e:
                status_box.write(f"❌ 自动归档失败: {save_e}")
        # ==========================

        status_box.update(label="✅ 所有工作已完成！", state="complete", expanded=False)
        st.rerun()

    except Exception as e:
        st.error(f"运行出错: {e}")


def render_step_final():
    state = st.session_state.newsroom_state
    st.subheader("📰 最终成稿")

    # === [修改点 1]: 增加了一个名为 "🐦 生成 X (推特) Thread" 的 Tab ===
    tab_text, tab_card, tab_twitter = st.tabs(["📄 文字稿件", "🖼️ 生成知识卡片", "🐦 生成 X (推特) Thread"])

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

    # === [修改点 2]: X Thread 终极免流汗发布方案 ===
    with tab_twitter:
        st.markdown("##### 🐦 X (Twitter) 发布生成器")
        st.caption("💡 拒绝手动粘贴 15 次！我们为您提供【一键排版工具流】或【蓝V长推文】方案。")
        
        # 让用户选择他们想要的推特格式
        twitter_mode = st.radio(
            "选择你的发布模式：",
            ["🧵 普通用户 Thread 模式 (配合 Typefully 一键发布)", "💎 X Premium (蓝V) 长推模式 (单条直发)"],
            horizontal=True
        )
        
        if st.button("🚀 生成推特专属文案", type="primary", use_container_width=True):
            from src.nodes.common import get_llm
            from langchain_core.messages import HumanMessage
            
            with st.spinner("AI 正在重构文案，适配推特生态..."):
                try:
                    llm = get_llm()
                    
                    if "Thread" in twitter_mode:
                        # 针对排版工具（如 Typefully）优化的 Prompt (严格字数限制版)
                        prompt = f"""
                        你是一个拥有百万粉丝的 X (Twitter) 科技大V。请将下文转化为适合 X 发布的 Thread（连推）。
                        
                        【🚨 致命字数限制（极度重要）】：
                        X 平台限制每条推文 280 字符（中文字符和 Emoji 各占 2 字符）。
                        因此，**每条推文的绝对上限是 130 个中文字符**！
                        你必须在这个极限框框内跳舞，绝对不能超字数，否则无法发布！
                        
                        【内容与排版要求】：
                        1. 黄金首推（1/N）：极具吸引力的 Hook，一句话点破痛点或抛出反常识结论。
                        2. 极高信息密度：在 130 字以内，每一推必须是一条完整的逻辑、一个震撼的数据或一句金句。删掉所有过渡性的废话（如"接下来我们看"、"总而言之"）。
                        3. 🚫 严禁使用 Markdown：绝对不要出现 `**加粗**`、`# 标题`、`- 列表` 等符号，X 平台不支持！
                        4. 🎨 视觉锚点：由于不能加粗，请在每推开头或关键数据前使用 1-2 个 Emoji（如 💡, 📊, ⚠️, 📌）作为视觉焦点。注意 Emoji 也会占字数，不要滥用。
                        5. 【排版工具指令】：为了让排版工具自动识别，每条推文之间，必须且只能使用连续的四个换行符（即空三行）隔开！
                        
                        【原文】：
                        {state["final_article"]}
                        """
                    else:
                        # 针对推特蓝V长推文（Long Tweet）优化的 Prompt (无严格字数限制)
                        prompt = f"""
                        你是一个拥有百万粉丝的 X (Twitter) 科技大V。请将下文转化为一篇【超长推文 (Long Tweet)】。
                        
                        【长推文排版要求】：
                        1. 蓝V不受字数限制，请勿切分成多条帖子，必须输出一篇完整的长文。
                        2. 🚫 严禁使用 Markdown：绝对不要出现 `**加粗**`、`# 标题` 等符号，这在 X 上显得极不专业！
                        3. 🎨 巧用 Emoji 划分结构：用 Emoji（如 🔹, 💡, 🚀, 📌 等）来替代 Markdown 的强调效果，作为段落标题或列表的引导。
                        4. 结构紧凑：第一段必须是极具吸引力的 Hook。多用短句，段落之间留出空行，确保手机端向下滚屏阅读极度丝滑。
                        5. 提炼干货：提取原文最核心的金句和数据，删减毫无意义的水词。
                        6. 结尾加上互动引导，如：你对这事怎么看？评论区见。
                        
                        【原文】：
                        {state["final_article"]}
                        """
                        
                    thread_result = llm.invoke([HumanMessage(content=prompt)]).content
                    # 终极物理清洗：彻底消灭 Markdown 的加粗和标题符
                    thread_result = thread_result.replace("**", "").replace("__", "").replace("### ", "").replace("## ", "").replace("# ", "")
                    state["twitter_thread"] = thread_result
                    st.rerun() 
                except Exception as e:
                    st.error(f"生成文案失败，请重试: {e}")
                    
        # 结果展示区
        if state.get("twitter_thread"):
            st.success("✅ 推特文案生成完毕！")
            
            if "Thread" in twitter_mode:
                st.info(
                    "💡 **终极省力发布指南 (只需粘贴 1 次)**：\n"
                    "1. 将鼠标悬停在下方代码框右上角，点击【Copy】复制全部文本。\n"
                    "2. 点击下方蓝色按钮，打开 **Typefully**（免费的顶级推特排版工具）。\n"
                    "3. 在 Typefully 的输入框中 `Ctrl+V` 粘贴，它会瞬间自动帮你切分成十几个推文，点击 Tweet 一键发送全部！"
                )
                # 使用 st.code 渲染，自带极简的一键复制按钮，并且保留严格的换行符
                st.code(state["twitter_thread"], language="markdown")
                st.link_button("🚀 前往 Typefully 极速发推", "https://typefully.com/new", type="primary", use_container_width=True)
                
            else:
                st.info("💡 **长推模式**：你选择了蓝V专享格式。只需点击右上角复制，直接在推特发布单条长推文即可！")
                st.code(state["twitter_thread"], language="markdown")
                # 长推模式直接唤起官方的单条发推接口
                import urllib.parse
                encoded_tweet = urllib.parse.quote(state["twitter_thread"])
                st.link_button("↗️ 唤起推特网页版直接发布", f"https://twitter.com/intent/tweet?text={encoded_tweet}", type="primary", use_container_width=True)


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
    """基于 HTML + dom-to-image-more 生成知识卡片，实现原生级字体清晰度"""
    import markdown
    import re

    html_content = markdown.markdown(content_md)
    clean_title = re.sub(r"[^\w\s-]", "", title).strip() or "newsroom_card"

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <!-- 【更改核心】弃用 html2canvas，改用 dom-to-image-more，原生 SVG 渲染字体绝对清晰 -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/dom-to-image-more/3.1.6/dom-to-image-more.min.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&display=swap');
            body {{
                background-color: #f0f2f6;
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                /* 强制使用系统最高质量字体组合 */
                font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
                text-rendering: optimizeLegibility;
            }}
            #card-container {{
                width: 480px; /* 稍微加宽一点，排版更好看 */
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
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 2px;
                opacity: 0.9;
                margin-bottom: 12px;
                border: 1px solid rgba(255,255,255,0.4);
                display: inline-block;
                padding: 4px 10px;
                border-radius: 20px;
            }}
            .card-title {{
                font-family: 'Noto Serif SC', "Microsoft YaHei", serif;
                font-size: 28px;
                font-weight: 700;
                line-height: 1.4;
                margin: 0;
                text-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            .card-body {{
                padding: 35px 30px;
                color: #2c3e50;
                font-size: 15px;
                line-height: 1.8;
                text-align: justify;
                background-image: radial-gradient(#f0f0f0 1px, transparent 1px);
                background-size: 20px 20px;
                background-color: #fff;
            }}
            .card-body h1, .card-body h2 {{
                font-size: 18px;
                color: #1a252f;
                margin-top: 25px;
                margin-bottom: 15px;
                border-left: 4px solid #4ca1af;
                padding-left: 12px;
            }}
            .card-body h3 {{ font-size: 16px; color: #333; margin-top: 15px; }}
            .card-body p {{ margin-bottom: 15px; }}
            .card-body strong {{ color: #000; font-weight: 700; }}
            .card-body ul, .card-body ol {{ padding-left: 20px; margin-bottom: 15px; }}
            .card-body li {{ margin-bottom: 8px; }}
            .card-body blockquote {{
                margin: 0 0 15px 0;
                padding: 10px 15px;
                background-color: #f8f9fa;
                border-left: 4px solid #cbd5e1;
                color: #64748b;
                font-style: italic;
            }}
            .card-footer {{
                background: #f8f9fa;
                padding: 20px 30px;
                text-align: center;
                font-size: 12px;
                color: #94a3b8;
                border-top: 1px dashed #e2e8f0;
            }}
            .dl-btn {{
                margin-top: 25px;
                padding: 14px 28px;
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 50px;
                font-size: 15px;
                font-weight: bold;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
                transition: transform 0.1s;
                font-family: -apple-system, "Microsoft YaHei", sans-serif;
            }}
            .dl-btn:active {{ transform: scale(0.95); }}
            .dl-btn:hover {{ background: #dc2626; }}
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
        <button class="dl-btn" onclick="downloadCard()">📸 保存为超清长图</button>
        <script>
            function downloadCard() {{
                const node = document.getElementById('card-container');
                const btn = document.querySelector('.dl-btn');
                btn.innerText = "⏳ 正在生成原画级图片...";
                
                // 设置 3 倍放大率，保证即使被微信/X平台压缩，文字依然锐利
                const scale = 3; 

                domtoimage.toPng(node, {{
                    width: node.offsetWidth * scale,
                    height: node.offsetHeight * scale,
                    style: {{
                        transform: 'scale(' + scale + ')',
                        transformOrigin: 'top left',
                        width: node.offsetWidth + 'px',
                        height: node.offsetHeight + 'px'
                    }},
                    bgcolor: '#ffffff'
                }})
                .then(function (dataUrl) {{
                    const link = document.createElement('a');
                    link.download = '{clean_title}_知识卡片.png';
                    link.href = dataUrl;
                    link.click();
                    btn.innerText = "📸 保存为超清长图";
                }})
                .catch(function (error) {{
                    console.error('图片生成错误:', error);
                    btn.innerText = "❌ 生成失败";
                    alert("图片生成失败，请检查浏览器控制台");
                }});
            }}
        </script>
    </body>
    </html>
    """

    import streamlit.components.v1 as comp
    # 调高了 iframe 的高度，避免因为内容过长出现双重滚动条
    comp.html(html_template, height=1200, scrolling=True)

