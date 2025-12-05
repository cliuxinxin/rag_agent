# frontend/views/deep_write.py
import streamlit as st
import json
import re
import time
import streamlit.components.v1 as comp

def render():
    st.header("✍️ 深度写作 (Beta)")
    
    # 初始化 session_state
    if "writing_project" not in st.session_state:
        st.session_state.writing_project = None
    if "current_writing_tab" not in st.session_state:
        st.session_state.current_writing_tab = "创建项目"
    
    # 顶部导航
    tab_create, tab_outline, tab_write, tab_publish = st.tabs(["📝 创建项目", "🧩 大纲编辑", "✏️ 正文写作", "📱 社交传播"])
    
    with tab_create:
        render_create_project()
    
    with tab_outline:
        if st.session_state.writing_project:
            render_outline_editor()
        else:
            st.info("请先在「创建项目」页创建写作项目。")
    
    with tab_write:
        if st.session_state.writing_project and st.session_state.writing_project.get('outline_data'):
            render_content_writer()
        else:
            st.info("请先在「大纲编辑」页生成文章大纲。")
    
    with tab_publish:
        if st.session_state.writing_project and st.session_state.writing_project.get('outline_data'):
            render_social_publisher()
        else:
            st.info("请先完成「正文写作」。")

def render_create_project():
    st.subheader("创建新项目")
    
    # 项目标题
    title = st.text_input("文章标题", placeholder="给你的文章起个吸引人的标题")
    
    # 用户需求
    requirement = st.text_area("写作需求", placeholder="描述你想写什么主题的文章，以及预期的读者群体和风格", height=120)
    
    # 文档上传
    st.markdown("#### 参考素材")
    uploaded_file = st.file_uploader("上传参考文档 (TXT/PDF)", type=["txt", "pdf"])
    doc_content = ""
    if uploaded_file:
        # 这里应该调用实际的文件处理函数
        doc_content = uploaded_file.getvalue().decode("utf-8")
        st.success(f"已上传: {uploaded_file.name}")
    
    # 创建按钮
    if st.button("🚀 创建写作项目", use_container_width=True):
        if not title or not requirement:
            st.error("请填写标题和写作需求")
            return
        
        # 初始化项目结构
        st.session_state.writing_project = {
            "title": title,
            "requirement": requirement,
            "document": doc_content,
            "full_content": doc_content,  # 用于 Context Caching
            "outline_data": [],
            "current_section_index": 0,
            "generated_sections": {},
            "social_summary": ""
        }
        
        st.success("项目创建成功！现在可以进入「大纲编辑」页。")
        st.rerun()

def render_outline_editor():
    project = st.session_state.writing_project
    st.subheader(f"🧩 大纲编辑: {project['title']}")
    
    # 显示当前大纲
    outline_data = project.get('outline_data', [])
    
    if not outline_data:
        st.info("尚未生成大纲，请点击下方按钮生成初始大纲。")
    else:
        st.markdown("#### 当前大纲")
        for i, section in enumerate(outline_data):
            with st.expander(f"第{i+1}章: {section['title']}", expanded=False):
                st.markdown(f"**描述**: {section['desc']}")
                if section.get('content'):
                    with st.container(border=True):
                        st.markdown(section['content'][:200] + "..." if len(section['content']) > 200 else section['content'])

    # 控制按钮
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧠 AI 自动生成大纲", use_container_width=True):
            if not project.get('full_content'):
                st.error("缺少文档内容，无法生成大纲")
                return
            
            # 调用 LangGraph 生成大纲
            from src.graphs.write_graph import research_graph
            initial_state = {
                "user_requirement": project["requirement"],
                "full_content": project["full_content"],
                "current_outline": [],
                "loop_count": 0,
                "planning_steps": [],
                "research_notes": [],
                "research_report": "",
                "current_section_index": 0,
                "current_section_content": "",
                "full_draft": "",
                "edit_instruction": ""
            }
            
            with st.spinner("AI 正在分析并生成大纲..."):
                for step in research_graph.stream(initial_state):
                    for node_name, update in step.items():
                        if "current_outline" in update:
                            st.session_state.writing_project["outline_data"] = update["current_outline"]
                            break
                
                st.success("大纲生成完成！")
                st.rerun()
    
    with col2:
        if st.button("🔁 重新生成", use_container_width=True):
            st.session_state.writing_project["outline_data"] = []
            st.rerun()
    
    with col3:
        instruction = st.text_input("修改指令", placeholder="如：增加一个关于技术挑战的章节")
        if st.button("🎨 AI 优化大纲", use_container_width=True) and instruction:
            if not outline_data:
                st.error("请先生成初始大纲")
                return
                
            from src.graphs.write_graph import refine_graph
            initial_state = {
                "user_requirement": project["requirement"],
                "full_content": project["full_content"],
                "current_outline": outline_data,
                "research_report": project.get("research_report", ""),
                "edit_instruction": instruction,
                "loop_count": 0,
                "planning_steps": [],
                "research_notes": [],
                "current_section_index": 0,
                "current_section_content": "",
                "full_draft": ""
            }
            
            with st.spinner("AI 正在优化大纲..."):
                for step in refine_graph.stream(initial_state):
                    for node_name, update in step.items():
                        if "current_outline" in update:
                            st.session_state.writing_project["outline_data"] = update["current_outline"]
                            if "research_report" in update:
                                st.session_state.writing_project["research_report"] = update["research_report"]
                            break
                
                st.success("大纲优化完成！")
                st.rerun()

def render_content_writer():
    project = st.session_state.writing_project
    outline_data = project["outline_data"]
    
    st.subheader(f"✏️ 正文写作: {project['title']}")
    
    # 章节选择器
    section_titles = [sec['title'] for sec in outline_data]
    selected_section = st.selectbox("选择章节", section_titles, 
                                  index=min(project.get("current_section_index", 0), len(section_titles)-1))
    
    # 找到选中章节的索引
    selected_index = section_titles.index(selected_section)
    project["current_section_index"] = selected_index
    section = outline_data[selected_index]
    
    # 显示章节描述
    st.markdown(f"**章节描述**: {section['desc']}")
    
    # 显示已生成的内容
    existing_content = section.get('content', '')
    if existing_content:
        st.markdown("#### 已生成内容:")
        st.markdown(existing_content)
    
    # 生成/重写按钮
    if st.button("🤖 AI 撰写本节内容" if not existing_content else "🔄 重新生成本节", use_container_width=True):
        from src.graphs.write_graph import drafting_graph
        
        # 构建已生成内容的上下文
        full_draft = ""
        for i in range(selected_index):
            full_draft += outline_data[i].get('content', '') + "\n\n"
        
        initial_state = {
            "user_requirement": project["requirement"],
            "full_content": project["full_content"],
            "research_report": project.get("research_report", ""),
            "current_outline": outline_data,
            "current_section_index": selected_index,
            "current_section_content": "",
            "full_draft": full_draft
        }
        
        with st.spinner(f"AI 正在撰写「{section['title']}」..."):
            for step in drafting_graph.stream(initial_state):
                for node_name, update in step.items():
                    if "current_section_content" in update:
                        # 更新项目内容
                        st.session_state.writing_project["outline_data"][selected_index]["content"] = update["current_section_content"]
                        break
            
            st.success("生成完成！")
            st.rerun()
    
    # 手动编辑区域
    st.markdown("#### 手动编辑:")
    manual_content = st.text_area("", value=existing_content, height=300, 
                                placeholder="你可以在这里手动编辑内容，或等待 AI 生成...")
    
    if st.button("💾 保存修改", use_container_width=True):
        st.session_state.writing_project["outline_data"][selected_index]["content"] = manual_content
        st.success("内容已保存！")

def render_social_publisher():
    project = st.session_state.writing_project
    st.subheader(f"📱 社交传播: {project['title']}")
    
    # 收集所有章节内容
    full_content = ""
    for section in project.get('outline_data', []):
        if section.get('content'):
            full_content += f"# {section['title']}\n\n{section['content']}\n\n"
    
    if not full_content.strip():
        st.info("请先完成正文写作。")
        return
    
    # 生成社交摘要
    if not project.get('social_summary'):
        with st.spinner("正在生成社交媒体摘要..."):
            from src.nodes.write_nodes import generate_viral_card_content
            project['social_summary'] = generate_viral_card_content(project['title'], full_content)
    
    # 显示摘要
    st.markdown("#### 社交媒体摘要")
    st.markdown(project['social_summary'])
    
    if st.button("🔄 重新生成摘要"):
        with st.spinner("正在重新生成社交媒体摘要..."):
            from src.nodes.write_nodes import generate_viral_card_content
            project['social_summary'] = generate_viral_card_content(project['title'], full_content)
            st.rerun()
    
    st.divider()
    
    # 知识长图预览
    st.subheader("🖼️ 知识长图预览")
    
    # 拼接正文 (用于 AI 摘要和 显示)
    full_markdown_display = ""
    full_markdown_text = ""
    
    for sec in project.get('outline_data', []):
        content = sec.get('content', '')
        if content:
            full_markdown_text += f"{sec['title']}\n{content}\n"
            # 这里稍微处理一下，让长图里的标题更明显
            full_markdown_display += f"## {sec['title']}\n\n{content}\n\n"

    if not full_markdown_display.strip():
        st.info("👈 请先在【正文写作】页生成文章内容。")
    else:
        col_view, col_action = st.columns([3, 1])
        with col_view:
            st.subheader("🖼️ 知识长图预览")
        with col_action:
            # 可以在这里放重置摘要的按钮
            if st.button("🔄 刷新导语"):
                st.session_state.writing_project['social_summary'] = ""
                st.rerun()

        # --- 自动生成导语 ---
        if not project.get('social_summary'):
             with st.spinner("正在提炼社交媒体摘要..."):
                 from src.nodes.write_nodes import generate_viral_card_content
                 st.session_state.writing_project['social_summary'] = generate_viral_card_content(project['title'], full_markdown_text)
        
        # --- 渲染 HTML ---
        import markdown
        html_body = markdown.markdown(full_markdown_display, extensions=['fenced_code'])
        summary_html = markdown.markdown(project['social_summary'])

        # CSS 样式：极致的去表格化，杂志风
        raw_title = project.get('title', '未命名文档')
        clean_title = re.sub(r'[^\w\s-]', '', raw_title).strip()
        clean_title = re.sub(r'[-\s]+', '-', clean_title)
        
        magazine_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700&family=Noto+Sans+SC:wght@400;700&display=swap" rel="stylesheet">
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    background-color: #f2f4f7;
                    font-family: 'Noto Sans SC', sans-serif;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }}
                
                #poster-node {{
                    width: 100%;
                    max-width: 450px;
                    background: white;
                    box-shadow: 0 15px 40px rgba(0,0,0,0.1);
                }}

                /* 头部 */
                .header-banner {{
                    background: #1a1a1a;
                    color: #f0f0f0;
                    padding: 60px 30px 40px;
                    text-align: left;
                    position: relative;
                }}
                .header-banner::after {{
                    content: '';
                    position: absolute;
                    bottom: 0;
                    left: 30px;
                    width: 40px;
                    height: 4px;
                    background: #ff4b4b;
                }}
                .header-title {{
                    font-family: 'Noto Serif SC', serif;
                    font-size: 28px;
                    line-height: 1.3;
                    font-weight: 700;
                    margin-bottom: 10px;
                }}
                .header-sub {{ opacity: 0.6; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; }}

                /* 导语区 */
                .summary-card {{ 
                    padding: 30px; 
                    background: #fff;
                    font-size: 14px; 
                    line-height: 1.7;
                    color: #555;
                    border-bottom: 1px solid #eee;
                }}
                .summary-card p {{ margin-bottom: 10px; }}
                .summary-card strong {{ color: #000; font-weight: 700; }}

                /* 正文区 */
                .content-body {{ padding: 30px; color: #222; line-height: 1.8; font-size: 15px; text-align: justify; }}
                
                h2 {{
                    margin-top: 40px;
                    margin-bottom: 20px;
                    font-size: 19px;
                    font-weight: 700;
                    color: #111;
                }}
                p {{ margin-bottom: 16px; }}
                
                blockquote {{
                    background: #f8f9fa;
                    border-left: 4px solid #4ca1af;
                    padding: 15px 20px;
                    margin: 20px 0;
                    color: #555;
                    border-radius: 0 8px 8px 0;
                }}
                
                pre {{
                    background: #2d2d2d;
                    color: #f8f8f2;
                    padding: 15px;
                    border-radius: 8px;
                    overflow-x: auto;
                    font-size: 12px;
                    margin: 15px 0;
                }}
                
                ul, ol {{ padding-left: 20px; }}
                li {{ margin-bottom: 8px; }}
            </style>
        </head>
        <body>
            <div id="poster-node">
                <div class="header-banner">
                    <div class="header-title">{raw_title}</div>
                    <div class="header-sub">DeepSeek 写作助手 · 精炼洞察</div>
                </div>
                
                <div class="summary-card">
                    {summary_html}
                </div>
                
                <div class="content-body">
                    {html_body}
                </div>
            </div>
            
            <div style="position: fixed; bottom: 30px; right: 30px; z-index: 999;">
                <button 
                    onclick="genImage()" 
                    style="background: #111; color: white; border: none; padding: 12px 25px; border-radius: 50px; font-weight: bold; box-shadow: 0 5px 15px rgba(0,0,0,0.2); cursor: pointer;"
                    onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 7px 20px rgba(0,0,0,0.3)';"
                    onmouseout="this.style.transform=''; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.2)';"
                >
                    📸 保存长图
                </button>
            </div>

            <script>
                function genImage() {{
                    var node = document.getElementById('poster-node');
                    html2canvas(node, {{
                        scale: 2,
                        useCORS: true,
                        scrollY: -window.scrollY
                    }}).then(canvas => {{
                        var link = document.createElement('a');
                        link.download = '{clean_title}_知识长图.png';
                        link.href = canvas.toDataURL("image/png");
                        link.click();
                    }});
                }}
            </script>
        </body>
        </html>"""

        # 渲染组件
        comp.html(magazine_html, height=800, scrolling=True)