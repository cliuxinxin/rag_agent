# frontend/views/ppt_gen.py
import streamlit as st
import os
from src.graphs.ppt_graph import ppt_graph
# 移除了 utils 导入，因为我们不再使用它

def render():
    st.header("📊 智能 PPT 生成器")
    st.caption("上传文档 -> AI 策划与撰写 -> 下载标准 PPTX")
    
    # 1. 输入区
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("上传文档 (PDF/TXT)", type=["pdf", "txt"])
    with col2:
        text_input = st.text_area("或粘贴文本", height=150)
        
    slides_count = st.slider("期望页数", min_value=5, max_value=20, value=10)
    
    if st.button("🚀 开始生成 PPT", type="primary"):
        full_text = ""
        doc_title = "未命名演示文稿"
        
        if uploaded_file:
            # 简单的读取逻辑，实际项目中可用 src.utils.load_file
            # 这里为了演示直接读文本，你也可以调用 PyPDFLoader
            try:
                # 复用你的 load_file_content 逻辑
                from frontend.views.deep_read import load_file_content
                full_text = load_file_content(uploaded_file)
                doc_title = uploaded_file.name.split(".")[0]
            except:
                st.error("文件解析失败")
                return
        elif text_input:
            full_text = text_input
            doc_title = text_input[:10].replace("\n", "")
            
        if not full_text:
            st.warning("请提供内容")
            return
            
        # 初始化状态
        initial_state = {
            "full_content": full_text,
            "doc_title": doc_title,
            "slides_count": slides_count,
            "ppt_outline": [],
            "final_ppt_content": [],
            "ppt_file_path": "",
            "run_logs": []
        }
        
        # 运行 Graph
        status_box = st.status("正在生成 PPT...", expanded=True)
        final_state = None
        
        try:
            for step in ppt_graph.stream(initial_state):
                for node_name, update in step.items():
                    if "run_logs" in update:
                        for log in update["run_logs"]:
                            status_box.write(log)
                    
                    # 可以在这里做中间态展示，比如大纲生成完后显示一下
                    if node_name == "Planner":
                        outline = update.get("ppt_outline", [])
                        status_box.write(f"🗺️ 大纲已生成，共 {len(outline)} 页")
                        
            final_state = update # 拿到最后的状态
            status_box.update(label="生成完成！", state="complete", expanded=True)
            
            # 显示下载按钮
            if final_state and final_state.get("ppt_file_path"):
                file_path = final_state["ppt_file_path"]
                with open(file_path, "rb") as f:
                    btn = st.download_button(
                        label="📥 点击下载 PPTX",
                        data=f,
                        file_name=os.path.basename(file_path),
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                    
        except Exception as e:
            st.error(f"运行出错: {e}")