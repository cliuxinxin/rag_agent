# src/graphs/copilot_graph.py
from langgraph.graph import StateGraph, END
from src.state import CopilotState
from src.embeddings import HunyuanEmbeddings
from src.db import create_copilot_session, STORAGE_DIR
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from src.nodes.common import get_llm
import json
import re
from pathlib import Path

# 初始化LLM实例
llm = get_llm()
llm_json_mode = get_llm().bind(response_format={"type": "json_object"})

# ==============================
# 初始化工作流节点
# ==============================

def text_formatter_node(state: CopilotState) -> CopilotState:
    """排版师节点：修复断行，插入二级标题，加粗核心实体"""
    raw_text = state["raw_text"]
    
    prompt = f"""
    你是专业的文本排版师，请将下面的无格式长文本进行优化排版，输出Markdown格式：
    要求：
    1. 修复断行和不合理的换行，将零散的句子合并成连贯的段落
    2. 每隔约800字根据语义插入 ## 二级标题，标题要能概括该部分内容
    3. 将段落中的核心实体、人名、专业术语、重要概念用 **加粗** 标出
    4. 保持原文内容100%不丢失，不修改原意，不添加额外内容
    5. 不需要添加一级标题，直接从二级标题开始
    
    原始文本：
    {raw_text}
    """
    
    response = llm.invoke(prompt)
    formatted_md = response.content.strip()
    
    return {
        "formatted_markdown": formatted_md
    }

def summarizer_node(state: CopilotState) -> CopilotState:
    """导读员节点：提取全文总结和核心看点"""
    formatted_md = state["formatted_markdown"]
    
    prompt = f"""
    请阅读下面的文章，提取：
    1. 一句话总结：用简洁的语言概括全文核心内容
    2. 核心看点：3-5个最有价值的要点，每个要点一句话
    
    输出严格为JSON格式，不要有其他内容：
    {{
        "summary": "一句话总结内容",
        "takeaways": [
            "核心看点1",
            "核心看点2",
            "核心看点3"
        ]
    }}
    
    文章内容：
    {formatted_md[:10000]}  # 限制长度避免token过长
    """
    
    response = llm_json_mode.invoke(prompt)
    try:
        summary_data = json.loads(response.content.strip())
    except:
        summary_data = {
            "summary": "文章总结生成失败",
            "takeaways": ["核心看点生成失败"]
        }
    
    return {
        "summary_data": summary_data
    }

def metadata_calc_node(state: CopilotState) -> CopilotState:
    """元数据计算节点：统计字数和阅读时间"""
    formatted_md = state["formatted_markdown"]
    
    # 统计纯文本字数（去除Markdown标记）
    text = re.sub(r'[#*_`~]', '', formatted_md)
    word_count = len(text)
    read_time = max(1, round(word_count / 400))  # 400字/分钟，至少1分钟
    
    return {
        "word_count": word_count,
        "read_time": read_time
    }

def vector_store_builder_node(state: CopilotState) -> CopilotState:
    """向量库构建节点：将Markdown切块存入FAISS"""
    formatted_md = state["formatted_markdown"]
    session_id = state["session_id"]
    
    # 按二级标题拆分
    headers_to_split_on = [
        ("##", "Header 2"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_header_splits = markdown_splitter.split_text(formatted_md)
    
    # 二次拆分
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )
    splits = text_splitter.split_documents(md_header_splits)
    
    # 构建FAISS向量库
    embeddings = HunyuanEmbeddings()
    vector_store = FAISS.from_documents(splits, embeddings)
    
    # 保存到本地
    faiss_path = STORAGE_DIR / f"copilot_{session_id}_faiss"
    vector_store.save_local(str(faiss_path))
    
    # 保存Markdown文件
    md_path = STORAGE_DIR / f"copilot_{session_id}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(formatted_md)
    
    return {
        "vector_store": vector_store
    }

def save_session_node(state: CopilotState) -> CopilotState:
    """保存会话到数据库"""
    summary_data = state["summary_data"]
    word_count = state["word_count"]
    read_time = state["read_time"]
    
    # 用总结的前30字作为标题
    title = summary_data["summary"][:30] + "..." if len(summary_data["summary"]) > 30 else summary_data["summary"]
    
    session_id = create_copilot_session(
        title=title,
        word_count=word_count,
        read_time=read_time,
        summary_data=summary_data
    )
    
    return {
        "session_id": session_id
    }

# ==============================
# 对话工作流节点
# ==============================

def context_router_node(state: CopilotState) -> CopilotState:
    """上下文路由节点：判断用选中文本还是向量检索"""
    selected_text = state.get("selected_text", "")
    session_id = state["session_id"]
    
    if selected_text and len(selected_text.strip()) > 0:
        # 有选中文本，直接使用
        return {
            "context": selected_text
        }
    else:
        # 没有选中文本，从FAISS检索
        query = state["user_query"]
        embeddings = HunyuanEmbeddings()
        faiss_path = STORAGE_DIR / f"copilot_{session_id}_faiss"
        vector_store = FAISS.load_local(str(faiss_path), embeddings, allow_dangerous_deserialization=True)
        docs = vector_store.similarity_search(query, k=3)
        context = "\n\n".join([doc.page_content for doc in docs])
        return {
            "context": context
        }

def responder_node(state: CopilotState) -> CopilotState:
    """解答者节点：根据上下文和操作类型生成回答"""
    action = state["action"]
    context = state["context"]
    user_query = state.get("user_query", "")
    
    action_prompts = {
        "explain": f"请详细解释下面这段文本的含义，把专业概念讲得通俗易懂：\n{context}",
        "translate": f"请将下面这段文本翻译成流畅的中文：\n{context}",
        "summarize": f"请总结下面这段文本的核心内容：\n{context}",
        "question": f"请基于下面的上下文回答问题：\n上下文：{context}\n问题：{user_query}"
    }
    
    prompt = action_prompts.get(action, action_prompts["question"])
    
    # 流式输出在路由层处理，这里只返回完整回答
    response = llm.invoke(prompt)
    
    return {
        "response": response.content.strip()
    }

# ==============================
# 构建工作流
# ==============================

def build_copilot_init_graph():
    """构建初始化排版工作流"""
    workflow = StateGraph(CopilotState)
    
    # 添加节点
    workflow.add_node("TextFormatter", text_formatter_node)
    workflow.add_node("Summarizer", summarizer_node)
    workflow.add_node("MetadataCalc", metadata_calc_node)
    workflow.add_node("SaveSession", save_session_node)
    workflow.add_node("VectorStoreBuilder", vector_store_builder_node)
    
    # 设置入口
    workflow.set_entry_point("TextFormatter")
    
    # 定义边
    workflow.add_edge("TextFormatter", "Summarizer")
    workflow.add_edge("Summarizer", "MetadataCalc")
    workflow.add_edge("MetadataCalc", "SaveSession")
    workflow.add_edge("SaveSession", "VectorStoreBuilder")
    workflow.add_edge("VectorStoreBuilder", END)
    
    return workflow.compile()

def build_copilot_chat_graph():
    """构建对话问答工作流"""
    workflow = StateGraph(CopilotState)
    
    # 添加节点
    workflow.add_node("ContextRouter", context_router_node)
    workflow.add_node("Responder", responder_node)
    
    # 设置入口
    workflow.set_entry_point("ContextRouter")
    
    # 定义边
    workflow.add_edge("ContextRouter", "Responder")
    workflow.add_edge("Responder", END)
    
    return workflow.compile()

# 创建单例供外部调用
copilot_init_graph = build_copilot_init_graph()
copilot_chat_graph = build_copilot_chat_graph()