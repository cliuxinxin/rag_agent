# frontend/views/deep_qa.py
import streamlit as st
from src.graphs.deep_qa_graph import deep_qa_graph as qa_graph
from src.storage import load_kbs
from src.db import list_kbs
from langchain_core.messages import HumanMessage

def render():
    st.header("❓ 深度追问")
    
    # 知识库选择
    with st.sidebar:
        st.subheader("🧠 知识库选择")
        all_kbs = list_kbs()
        selected_kbs = st.multiselect("选择知识库", all_kbs, default=all_kbs[0] if all_kbs else None)
    
    # 项目创建
    if "qa_project" not in st.session_state:
        st.session_state.qa_project = None
    
    if not st.session_state.qa_project:
        st.subheader("创建 QA 项目")
        title = st.text_input("项目标题", placeholder="给你的 QA 项目起个名字")
        topic = st.text_area("主题/领域", placeholder="描述你要深入探讨的主题或领域", height=100)
        
        if st.button("🚀 创建项目"):
            if not title or not topic:
                st.error("请填写项目标题和主题")
                return
            
            st.session_state.qa_project = {
                "title": title,
                "topic": topic,
                "qa_pairs": [],
                "current_question": "",
                "final_report": ""
            }
            st.success("项目创建成功！")
            st.rerun()
        return
    
    # 显示项目信息
    project = st.session_state.qa_project
    st.subheader(f"项目: {project['title']}")
    st.markdown(f"**主题**: {project['topic']}")
    
    # 显示已有问答对
    if project['qa_pairs']:
        st.markdown("### 💬 已有问答")
        for i, qa in enumerate(project['qa_pairs']):
            with st.expander(f"Q{i+1}: {qa['question'][:50]}{'...' if len(qa['question']) > 50 else ''}"):
                st.markdown(f"**问题**: {qa['question']}")
                st.markdown(f"**答案**: {qa['answer']}")
    
    # 提出新问题
    st.markdown("### ❓ 提出新问题")
    new_question = st.text_area("输入你的问题", 
                              value=project.get('current_question', ''),
                              placeholder="请输入你想深入了解的问题...",
                              height=100)
    
    if st.button("🔍 深度分析"):
        if not new_question:
            st.error("请输入问题")
            return
        
        if not selected_kbs:
            st.error("请选择至少一个知识库")
            return
        
        # 加载知识库
        with st.spinner("加载知识库..."):
            source_documents, vector_store = load_kbs(selected_kbs)
        
        # 构建初始状态
        initial_state = {
            "messages": [HumanMessage(content=new_question)],
            "source_documents": source_documents,
            "vector_store": vector_store,
            "next": "Supervisor",
            "current_search_query": "",
            "final_evidence": [],
            "loop_count": 0,
            "attempted_searches": [],
            "research_notes": [],
            "failed_topics": [],
            "full_content": "",
            "doc_title": "",
            "current_question": new_question,
            "qa_pairs": project['qa_pairs'],
            "final_report": project.get('final_report', '')
        }
        
        # 运行图
        with st.spinner("AI 正在深度分析..."):
            final_answer = ""
            for step in qa_graph.stream(initial_state):
                for node_name, update in step.items():
                    if "messages" in update and update["messages"]:
                        final_answer = update["messages"][-1].content
            
            # 保存问答对
            st.session_state.qa_project['qa_pairs'].append({
                "question": new_question,
                "answer": final_answer
            })
            st.session_state.qa_project['current_question'] = ""
            
            st.success("分析完成！")
            st.rerun()
    
    # 生成总结报告
    if project['qa_pairs']:
        st.markdown("### 📝 总结报告")
        if project.get('final_report'):
            st.markdown(project['final_report'])
        
        if st.button("📊 生成总结报告"):
            if not selected_kbs:
                st.error("请选择至少一个知识库")
                return
            
            # 加载知识库
            with st.spinner("加载知识库..."):
                source_documents, vector_store = load_kbs(selected_kbs)
            
            # 构建初始状态
            initial_state = {
                "messages": [HumanMessage(content=f"基于以下问答对生成总结报告:\n\n" + 
                                         "\n\n".join([f"Q: {qa['question']}\nA: {qa['answer']}" for qa in project['qa_pairs']]))],
                "source_documents": source_documents,
                "vector_store": vector_store,
                "next": "Supervisor",
                "current_search_query": "",
                "final_evidence": [],
                "loop_count": 0,
                "attempted_searches": [],
                "research_notes": [],
                "failed_topics": [],
                "full_content": "",
                "doc_title": "",
                "current_question": "",
                "qa_pairs": project['qa_pairs'],
                "final_report": ""
            }
            
            # 运行图
            with st.spinner("AI 正在生成总结报告..."):
                final_answer = ""
                for step in qa_graph.stream(initial_state):
                    for node_name, update in step.items():
                        if "messages" in update and update["messages"]:
                            final_answer = update["messages"][-1].content
                
                st.session_state.qa_project['final_report'] = final_answer
                st.success("总结报告生成完成！")
                st.rerun()
    
    # 重置项目
    if st.button("🔄 重置项目"):
        st.session_state.qa_project = None
        st.rerun()