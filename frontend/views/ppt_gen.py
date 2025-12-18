# frontend/views/ppt_gen.py
import streamlit as st
import os
from src.graphs.ppt_graph import ppt_graph
from frontend.views.deep_read import load_file_content
# === [修改] 适配 Langfuse v3 ===
try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:
    LangfuseCallbackHandler = None 

def render():
    st.header("📊 智能 PPT 生成器 (内存模式)")
    st.caption("上传文档 -> AI 策划与撰写 -> 极速生成下载")
    
    # === 1. 初始化 Session State ===
    if "ppt_binary_data" not in st.session_state:
        st.session_state.ppt_binary_data = None
    if "ppt_filename" not in st.session_state:
        st.session_state.ppt_filename = "presentation.pptx"

    # === 2. 输入区 ===
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader("上传文档 (PDF/TXT)", type=["pdf", "txt"])
    with col2:
        text_input = st.text_area("或粘贴文本", height=150)
        
    slides_count = st.slider("期望页数", min_value=5, max_value=20, value=10)
    
    # === 3. 生成逻辑 ===
    if st.button("🚀 开始生成 PPT", type="primary"):
        full_text = ""
        doc_title = "demo"
        
        if uploaded_file:
            try:
                full_text = load_file_content(uploaded_file)
                doc_title = uploaded_file.name.split(".")[0]
            except:
                st.error("文件解析失败")
                return
        elif text_input:
            full_text = text_input
            doc_title = text_input[:10].replace("\n", "").strip() or "demo"
            
        if not full_text:
            st.warning("请提供内容")
            return
            
        # 清理文件名非法字符
        safe_name = "".join([c for c in doc_title if c.isalnum() or c in (' ','-','_')])
        if not safe_name: safe_name = "presentation"
            
        initial_state = {
            "full_content": full_text,
            "doc_title": doc_title,
            "slides_count": slides_count,
            "ppt_outline": [],
            "final_ppt_content": [],
            "ppt_binary": None, # 初始化为空
            "run_logs": []
        }
        
        with st.status("正在生成 PPT...", expanded=True) as status_box:
            final_state = None
            try:
                # === [修改] PPT Callback ===
                ppt_config = {}
                if LangfuseCallbackHandler:
                    handler = LangfuseCallbackHandler()
                    ppt_config["callbacks"] = [handler]
                    ppt_config["metadata"] = {
                        "langfuse_tags": ["ppt-gen"]
                    }
                
                for step in ppt_graph.stream(initial_state, config=ppt_config):
                    for node_name, update in step.items():
                        if "run_logs" in update:
                            for log in update["run_logs"]:
                                status_box.write(log)
                        
                        if node_name == "Planner":
                            outline = update.get("ppt_outline", [])
                            status_box.write(f"🗺️ 大纲已生成，共 {len(outline)} 页")
                
                final_state = update
                status_box.update(label="生成完成！", state="complete", expanded=False)
                
                # === 存入 Session State (核心) ===
                if final_state and final_state.get("ppt_binary"):
                    st.session_state.ppt_binary_data = final_state["ppt_binary"]
                    st.session_state.ppt_filename = f"{safe_name}.pptx"
                    # 刷新页面，让下载按钮从 Session State 中渲染
                    st.rerun()
                    
            except Exception as e:
                st.error(f"运行出错: {e}")

    # === 4. 下载区域 ===
    # 直接使用内存数据，完全不依赖文件系统
    if st.session_state.ppt_binary_data:
        st.divider()
        st.success(f"✅ PPT 已就绪: {st.session_state.ppt_filename}")
        
        col_dl, col_reset = st.columns([1, 4])
        
        with col_dl:
            st.download_button(
                label="📥 点击下载 PPTX",
                data=st.session_state.ppt_binary_data, # 直接传入 bytes
                file_name=st.session_state.ppt_filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key="download_ppt_btn"
            )
        
        with col_reset:
            if st.button("🔄 开始新任务"):
                st.session_state.ppt_binary_data = None
                st.rerun()