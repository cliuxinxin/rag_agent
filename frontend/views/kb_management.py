# frontend/views/kb_management.py
import streamlit as st
from src.storage import list_kbs, delete_kb, get_kb_details, save_kb
from src.utils import load_file, split_documents
from langchain_core.documents import Document

def render():
    st.header("📂 知识库管理")
    tabs = st.tabs(["📚 知识库列表 & 检视", "➕ 新建/追加知识"])
    
    with tabs[0]:
        existing_kbs = list_kbs()
        if not existing_kbs:
            st.info("暂无知识库。")
        else:
            col_list, col_detail = st.columns([1, 2])
            with col_list:
                st.subheader("知识库列表")
                selected_kb_to_view = st.radio("选择知识库查看详情", existing_kbs)
                st.markdown("---")
                if st.button(f"🗑️ 删除 {selected_kb_to_view}", type="primary"):
                    delete_kb(selected_kb_to_view)
                    st.success(f"已删除 {selected_kb_to_view}")
                    st.rerun()
            
            with col_detail:
                # 获取增强后的详情
                details = get_kb_details(selected_kb_to_view)
                
                # === 标题栏 + 状态徽章 ===
                st.subheader(f"🔍 检视: {selected_kb_to_view}")
                
                status = details["health_status"]
                if status == "healthy":
                    st.success(f"✅ 状态健康 (完整度 100%)")
                elif status == "mismatch":
                    loss = details['doc_count'] - details['vector_count']
                    st.error(f"⚠️ 数据不一致！丢失 {loss} 个向量片段 (建议重新生成)")
                elif status == "corrupted":
                    st.error("❌ 索引文件损坏，无法读取")
                else:
                    st.warning("⚪ 空知识库")

                # === 核心指标对比 ===
                m1, m2, m3 = st.columns(3)
                m1.metric("原始片段 (JSON)", details["doc_count"])
                
                # 如果数量不一致，用红色显示向量数
                vec_label = "向量索引 (FAISS)"
                vec_val = details["vector_count"]
                if status == "mismatch":
                    delta_color = "inverse"  # 显示红色下降箭头
                    m2.metric(vec_label, vec_val, delta=f"{vec_val - details['doc_count']}", delta_color=delta_color)
                else:
                    m2.metric(vec_label, vec_val)

                m3.metric("总字符数", f"{details['total_chars'] / 1000:.1f}k")
                
                st.divider()
                
                # === 调试信息 ===
                with st.expander("📊 详细统计信息", expanded=True):
                    st.write(f"**语言**: {', '.join(details['languages']) if details['languages'] else '未指定'}")
                    st.write(f"**存储路径**: `storage/{selected_kb_to_view}_faiss/index.faiss`")
                    if status == "mismatch":
                        st.caption("💡 提示：'原始片段'来自 JSON 备份，'向量索引'来自实际 FAISS 数据库。如果不一致，说明在向量化过程中发生了中断或错误。")

                st.write("📄 **内容预览**")
                if details["preview"]:
                    for item in details["preview"]:
                        with st.container(border=True):
                            st.caption(f"来源: {item['source']}")
                            st.text(item['content'])
                else:
                    st.caption("无预览内容")
    
    with tabs[1]:
        st.subheader("上传文档")
        kb_action = st.radio("模式", ["追加到现有", "新建知识库"], horizontal=True)
        target_kb_name = ""
        if kb_action == "追加到现有":
            if existing_kbs:
                target_kb_name = st.selectbox("选择目标库", existing_kbs)
            else:
                st.warning("请先新建")
        else:
            target_kb_name = st.text_input("新库名称 (英文/数字)", placeholder="kb_v1")
        kb_language = st.selectbox("文档主要语言", ["Chinese", "English"], index=0)
        
        upload_mode = st.tabs(["📁 上传文件", "📝 粘贴文本"])
        raw_docs = []
        with upload_mode[0]:
            uploaded_files = st.file_uploader("支持 PDF/TXT", type=["pdf", "txt"], accept_multiple_files=True)
        with upload_mode[1]:
            text_input = st.text_area("输入文本", height=150)
        
        if st.button("💾 开始处理并保存", use_container_width=True):
            if not target_kb_name:
                st.error("请输入名称")
                return
            if uploaded_files:
                for f in uploaded_files:
                    raw_docs.extend(load_file(f))
            if text_input:
                from langchain_core.documents import Document
                raw_docs.append(Document(page_content=text_input, metadata={"source": "text_input"}))
            if not raw_docs:
                st.warning("没有内容可保存。")
                return
            chunks = split_documents(raw_docs, chunk_size=800)
            st.info(f"已切分为 {len(chunks)} 个片段 (Chunk Size=800)")
            progress_bar = st.progress(0, text="初始化向量化...")
            try:
                save_kb(target_kb_name, chunks, language=kb_language, progress_bar=progress_bar)
                st.success("✅ 保存成功！")
                st.rerun()
            except Exception as e:
                st.error(f"保存失败: {e}")