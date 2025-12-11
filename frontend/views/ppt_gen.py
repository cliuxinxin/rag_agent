# frontend/views/ppt_gen.py
import streamlit as st
import os
from src.graphs.ppt_graph import ppt_graph
# 确保引用路径正确
from frontend.views.deep_read import load_file_content 

def render():
    st.header("📊 智能 PPT 生成器")
    st.caption("上传文档 -> AI 策划与撰写 -> 下载标准 PPTX")
    
    # === 1. 初始化 Session State ===
    # 这一步是为了防止点击下载按钮后，生成结果丢失
    if "ppt_result" not in st.session_state:
        st.session_state.ppt_result = None

    # === 2. 输入区 ===
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("上传文档 (PDF/TXT)", type=["pdf", "txt"])
    with col2:
        text_input = st.text_area("或粘贴文本", height=150)
        
    slides_count = st.slider("期望页数", min_value=5, max_value=20, value=10)
    
    # === 3. 生成逻辑 (点击后运行，存入 State) ===
    if st.button("🚀 开始生成 PPT", type="primary"):
        full_text = ""
        doc_title = "未命名演示文稿"
        
        # 处理输入
        if uploaded_file:
            try:
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
            
        # 初始化 Graph 输入
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
        with st.status("正在生成 PPT...", expanded=True) as status_box:
            final_state = None
            try:
                for step in ppt_graph.stream(initial_state):
                    for node_name, update in step.items():
                        if "run_logs" in update:
                            for log in update["run_logs"]:
                                status_box.write(log)
                        
                        if node_name == "Planner":
                            outline = update.get("ppt_outline", [])
                            status_box.write(f"🗺️ 大纲已生成，共 {len(outline)} 页")
                
                # 这里的 update 是最后一步的状态
                final_state = update 
                status_box.update(label="生成完成！", state="complete", expanded=False)
                
                # === 关键点：将结果存入 Session State ===
                if final_state and final_state.get("ppt_file_path"):
                    st.session_state.ppt_result = {
                        "path": final_state["ppt_file_path"],
                        "title": os.path.basename(final_state["ppt_file_path"])
                    }
                    # 强制重新运行一次，以便跳出 if st.button 块，进入下面的下载展示块
                    # 这样可以防止第一次生成后不显示下载按钮的问题
                    st.rerun() 
                    
            except Exception as e:
                st.error(f"运行出错: {e}")

    # === 4. 展示与下载区域 (在 Button 逻辑块之外) ===
    # 只要 State 里有结果，就一直显示下载按钮，不会因为刷新而消失
    if st.session_state.ppt_result:
        st.divider()
        st.success(f"✅ PPT 已就绪: {st.session_state.ppt_result['title']}")
        
        result = st.session_state.ppt_result
        file_path = result["path"]
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 将文件读取到内存中，防止文件句柄在刷新时丢失导致下载中断
            with open(file_path, "rb") as f:
                file_data = f.read()
                
            col_dl, col_reset = st.columns([1, 4])
            
            with col_dl:
                st.download_button(
                    label="📥 点击下载 PPTX",
                    data=file_data, # 传入二进制数据而不是文件句柄
                    file_name=result["title"],
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="download_ppt_btn"
                )
            
            with col_reset:
                # 提供一个重置按钮，用来清空 State，开始新任务
                if st.button("🔄 开始新任务"):
                    st.session_state.ppt_result = None
                    st.rerun()
        else:
            st.error("文件已丢失，请重新生成。")