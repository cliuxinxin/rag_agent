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
    results = retriever.search(question, k=3)
    
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
    """重写查询。"""
    question = state["question"]
    
    # 初始化 LLM (DeepSeek)
    llm = get_llm()
    
    msg = [
        SystemMessage(content="""之前的搜索未找到相关结果。
        请根据用户原问题，重写一个更适合BM25关键词搜索的查询字符串。
        只输出新的查询语句。"""),
        HumanMessage(content=f"Original: {question}")
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