# frontend/views/kb_management.py
import streamlit as st
from src.storage import list_kbs, delete_kb, get_kb_details, save_kb, resume_kb_embedding, search_kb_chunks, get_chunk_vector
from src.utils import load_file, split_documents
from langchain_core.documents import Document
from src.logger import get_logger

logger = get_logger("View_KBManagement")

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
                
                # [新增] 切换知识库时，清空之前的搜索结果，防止串台
                if "last_kb" not in st.session_state:
                    st.session_state.last_kb = selected_kb_to_view
                if st.session_state.last_kb != selected_kb_to_view:
                    st.session_state.search_results = None
                    st.session_state.vector_view_data = {}
                    st.session_state.last_kb = selected_kb_to_view
                
                st.markdown("---")
                if st.button(f"🗑️ 删除 {selected_kb_to_view}", type="primary"):
                    delete_kb(selected_kb_to_view)
                    st.success(f"已删除 {selected_kb_to_view}")
                    st.session_state.search_results = None  # 删除后清空结果
                    st.session_state.vector_view_data = {}
                    st.rerun()
            
            with col_detail:
                # 获取增强后的详情
                details = get_kb_details(selected_kb_to_view)
                
                # === 标题栏 + 状态徽章 ===
                st.subheader(f"🔍 检视: {selected_kb_to_view}")
                
                status = details["health_status"]
                
                # ----------------- 新增修复逻辑开始 -----------------
                if status == "mismatch":
                    loss = details['doc_count'] - details['vector_count']
                    st.error(f"⚠️ 数据不一致！丢失 {loss} 个向量片段。")
                    
                    st.markdown(f"""
                    **当前进度**: {details['vector_count']} / {details['doc_count']}
                    
                    这可能是由于生成过程中断、网络超时或强制关闭导致的。
                    点击下方按钮可以**从断点处继续生成**，无需从头开始。
                    """)
                    
                    # 修复按钮
                    if st.button("🔄 断点续传 / 修复索引", type="primary", use_container_width=True):
                        progress_bar = st.progress(0.0, text="正在读取进度...")
                        try:
                            curr, total = resume_kb_embedding(
                                selected_kb_to_view, 
                                batch_size=50,  # 稍微加大批次
                                progress_bar=progress_bar
                            )
                            if curr == total:
                                st.success("✅ 修复完成！索引已完整。")
                                st.rerun()
                            else:
                                st.warning(f"本轮处理结束，当前进度 {curr}/{total}。如果还没完，请再次点击继续。")
                                st.rerun()
                        except Exception as e:
                            st.error(f"修复过程中断: {e}")
                            logger.error(f"修复知识库 {selected_kb_to_view} 时出错: {e}", exc_info=True)
                            
                elif status == "corrupted":
                    st.error("❌ 索引文件完全损坏，无法读取。建议删除重建。")
                # ----------------- 新增修复逻辑结束 -----------------
                
                elif status == "healthy":
                    st.success(f"✅ 状态健康 (完整度 100%)")
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
                
                st.divider()
                
                # === 核心新增：搜索功能 (带状态保持) ===
                st.subheader("🔎 深度调试：内容与向量透视")
                
                # 初始化 session_state
                if "search_results" not in st.session_state:
                    st.session_state.search_results = None
                if "vector_view_data" not in st.session_state:
                    st.session_state.vector_view_data = {}  # 用于存每个片段的向量显示状态

                col_search, col_btn = st.columns([4, 1])
                with col_search:
                    search_kw = st.text_input("输入关键词搜索片段", placeholder="例如：LangGraph, 内存...")
                with col_btn:
                    do_search = st.button("搜索", use_container_width=True)

                # --- 逻辑修改点：将搜索结果存入 session_state ---
                if do_search and search_kw:
                    with st.spinner("搜索中..."):
                        results = search_kb_chunks(selected_kb_to_view, search_kw)
                        st.session_state.search_results = results
                        # 重置之前的向量查看状态
                        st.session_state.vector_view_data = {}
                
                # --- 渲染区域：始终从 session_state 读取 ---
                if st.session_state.search_results is not None:
                    results = st.session_state.search_results
                    st.caption(f"找到 {len(results)} 个匹配片段 (仅显示前 20 个)")
                    
                    if not results:
                        st.warning("未找到匹配内容")
                    else:
                        for item in results:
                            chunk_id = item['id']
                            content = item['content']
                            meta = item['metadata']
                            
                            with st.expander(f"片段 #{chunk_id} | {content[:30]}...", expanded=False):
                                c1, c2 = st.columns([2, 1])
                                
                                with c1:
                                    st.markdown("**📄 原始内容**")
                                    st.text_area("Content", content, height=150, key=f"txt_{chunk_id}", disabled=True, label_visibility="collapsed")
                                    st.json(meta, expanded=False)
                                    
                                with c2:
                                    st.markdown("**📐 向量数据 (FAISS)**")
                                    
                                    # 使用 toggle 或者记录状态，防止刷新后消失
                                    # 这里我们用一个字典记录谁被点击了
                                    btn_key = f"btn_vec_{chunk_id}"
                                    
                                    # 如果点击了按钮，切换状态
                                    if st.button(f"查看/隐藏向量 #{chunk_id}", key=btn_key):
                                        if chunk_id in st.session_state.vector_view_data:
                                            del st.session_state.vector_view_data[chunk_id]
                                        else:
                                            # 获取数据并存入状态
                                            vec_data = get_chunk_vector(selected_kb_to_view, chunk_id)
                                            st.session_state.vector_view_data[chunk_id] = vec_data

                                    # 检查当前 ID 是否在显示列表里
                                    if chunk_id in st.session_state.vector_view_data:
                                        vec_data = st.session_state.vector_view_data[chunk_id]
                                        
                                        if vec_data["exists"]:
                                            vec = vec_data["vector"]
                                            dim = vec_data["dimension"]
                                            
                                            st.success(f"✅ 维度: {dim}")
                                            st.write("前 10 维数值:")
                                            st.code(str(vec[:10]), language="json")
                                            
                                            if all(v == 0 for v in vec):
                                                st.error("⚠️ 警告：全零向量！")
                                            else:
                                                st.info("数据看起来正常 (非全零)")
                                        else:
                                            st.error(f"❌ 无法获取: {vec_data['msg']}")
                                            if status == "mismatch":
                                                st.caption("原因可能是数据不一致，JSON 里的 ID 在 FAISS 里找不到。")
    
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