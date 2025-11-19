"""LangGraph 节点逻辑实现。"""

import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.state import AgentState
from src.bm25 import SimpleBM25Retriever


def get_llm():
    """获取LLM实例。"""
    return ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        temperature=0.1
    )


def retrieve(state: AgentState) -> dict:
    """使用 BM25 检索文档。"""
    question = state["question"]
    source_docs = state.get("source_documents", [])

    if not source_docs:
        return {"retrieved_documents": []}

    # 在内存中构建检索器 (针对无向量库场景)
    retriever = SimpleBM25Retriever(source_docs)
    results = retriever.search(question, k=10)
    
    return {"retrieved_documents": results}


def grade_documents(state: AgentState) -> dict:
    """评估文档相关性。"""
    question = state["question"]
    docs = state["retrieved_documents"]
    filtered_docs = []

    # 初始化 LLM (DeepSeek)
    llm = get_llm()

    system_prompt = (
        "你是一个文档评估员。判断文档内容是否包含回答用户问题所需的信息。"
        "只需回答 'yes' 或 'no'。"
    )

    for doc in docs:
        msg = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Doc: {doc.page_content}\n\nQuery: {question}")
        ]
        grade = llm.invoke(msg).content.lower()
        if "yes" in grade:
            filtered_docs.append(doc)

    # 如果没有文档通过筛选，标记需要重新搜索
    search_needed = len(filtered_docs) == 0
    return {"retrieved_documents": filtered_docs, "search_needed": search_needed}


def transform_query(state: AgentState) -> dict:
    """重写查询：根据知识库语言生成对应的搜索关键词。"""
    question = state["question"]
    source_docs = state.get("source_documents", [])
    
    # 1. 检测知识库的主要语言
    # 从 metadata 中提取语言，统计出现最多的语言
    languages = [doc.metadata.get("language", "Chinese") for doc in source_docs]
    
    if languages:
        # 获取出现频率最高的语言作为目标语言
        target_language = max(set(languages), key=languages.count)
    else:
        target_language = "Chinese" # 默认

    # 初始化 LLM (DeepSeek)
    llm = get_llm()
    
    # 2. 构建提示词，强制要求转换为目标语言
    msg = [
        SystemMessage(content=f"""你是一个专业的搜索引擎优化专家。
        目前的知识库主要语言是：【{target_language}】。
        
        之前的直接搜索效果不佳。请执行以下操作：
        1. 分析用户的问题意图。
        2. 将问题转换为【{target_language}】（如果原问题已经是该语言，则进行同义词扩展）。
        3. 生成最适合 BM25 关键词匹配的查询字符串。
        
        只输出新的查询语句，不要包含任何解释。"""),
        HumanMessage(content=f"User Query: {question}")
    ]
    
    new_query = llm.invoke(msg).content
    
    return {
        "question": new_query,
        "search_count": state.get("search_count", 0) + 1
    }


def generate(state: AgentState) -> dict:
    """生成最终回答。"""
    question = state["question"]
    docs = state["retrieved_documents"]
    
    # 初始化 LLM (DeepSeek)
    llm = get_llm()
    
    context = "\n\n".join([d.page_content for d in docs])
    
    prompt = f"""基于以下参考文档回答问题。如果无法回答，请说明。
    
    [上下文]
    {context}
    
    [问题]
    {question}
    """
    response = llm.invoke(prompt)
    return {"generation": response.content}