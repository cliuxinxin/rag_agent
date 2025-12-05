# src/nodes/chat_nodes.py
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from src.state import AgentState
from src.nodes.common import get_llm

# === Supervisor ===

class RouteResponse(BaseModel):
    observed_gap: str = Field(..., description="分析信息缺口")
    next: Literal["Searcher", "Answerer"] = Field(..., description="下一步角色")
    search_query: str = Field(default="", description="搜索指令")
    reasoning: str = Field(..., description="理由")

def supervisor_node(state: AgentState) -> dict:
    messages = state["messages"]
    current_loop = state.get("loop_count", 0)
    past_searches = state.get("attempted_searches", [])
    failed_topics = state.get("failed_topics", [])
    
    MAX_LOOPS = 6 
    llm = get_llm()
    
    history_str = "\n".join([f"- {q}" for q in past_searches]) if past_searches else "无"
    failed_str = "\n".join([f"- {q}" for q in failed_topics]) if failed_topics else "无"

    if current_loop >= MAX_LOOPS:
        return {"next": "Answerer", "current_search_query": "", "loop_count": current_loop}

    parser = PydanticOutputParser(pydantic_object=RouteResponse)
    format_instructions = parser.get_format_instructions()

    # 这里建议以后也提取到 src/prompts.py
    system_prompt = f"""你是一个全能型的研究项目主管。
    当前研究轮次：{current_loop + 1} / {MAX_LOOPS}。
    【已尝试的搜索】{history_str}
    【❌ 无结果话题】{failed_str}
    
    请分析现状，识别信息缺口，指派 Searcher 或 Answerer。
    {format_instructions}
    """
    
    try:
        response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
        content = response.content.strip().replace("```json", "").replace("```", "")
        decision = parser.parse(content)
    except Exception as e:
        print(f"Supervisor Error: {e}")
        decision = RouteResponse(
            observed_gap="Error", next="Answerer", search_query="", reasoning="System Error"
        )

    return {
        "next": decision.next,
        "current_search_query": decision.search_query,
        "loop_count": current_loop + 1
    }

# === Searcher ===

def search_node(state: AgentState) -> dict:
    query = state.get("current_search_query", "")
    source_docs = state.get("source_documents", [])
    vector_store = state.get("vector_store", None)
    
    if not query:
        return {"messages": [AIMessage(content="Searcher: 指令为空。", name="Searcher")]}

    llm = get_llm()

    # 简单扩充关键词
    expansion_prompt = f"针对搜索意图 '{query}'，生成 3-4 个关键词，空格分隔。"
    bm25_keywords = llm.invoke([HumanMessage(content=expansion_prompt)]).content.strip().replace('"', '')
    
    results_bm25 = []
    results_vector = []

    if source_docs:
        try:
            bm25_retriever = BM25Retriever.from_documents(source_docs)
            bm25_retriever.k = 10 
            results_bm25 = bm25_retriever.invoke(f"{query} {bm25_keywords}")
        except: pass
    
    if vector_store:
        try:
            vector_retriever = vector_store.as_retriever(search_kwargs={"k": 10})
            results_vector = vector_retriever.invoke(query)
        except: pass

    # 合并去重
    all_results = results_vector + results_bm25
    unique_docs = {}
    for doc in all_results:
        if doc.page_content not in unique_docs:
            unique_docs[doc.page_content] = doc
    
    final_docs = list(unique_docs.values())[:6]

    if not final_docs:
        return {
            "messages": [AIMessage(content=f"Searcher: 未找到相关信息。", name="Searcher")],
            "attempted_searches": [query],
            "failed_topics": [query]
        }

    # 笔记生成
    context_text = "\n\n".join([f"[Ref {i+1}] {d.page_content}" for i, d in enumerate(final_docs)])
    filter_prompt = f"任务: '{query}'\n资料:\n{context_text}\n请提取关键信息。"
    extraction = llm.invoke([HumanMessage(content=filter_prompt)]).content
    
    current_note = f"### 🔍 搜索主题: {query} (关键词: {bm25_keywords})\n{extraction}\n"

    return {
        "messages": [AIMessage(content=f"【搜索报告】\n方向: {query}\n发现:\n{extraction}", name="Searcher")],
        "final_evidence": final_docs,
        "attempted_searches": [query],
        "research_notes": [current_note]
    }

# === Answerer ===

def answer_node(state: AgentState) -> dict:
    messages = state["messages"]
    evidences = state.get("final_evidence", [])
    notes = state.get("research_notes", [])
    llm = get_llm()
    
    notes_text = "【🕵️‍♂️ 调查笔记】\n" + "\n".join(notes) if notes else "无调查记录。"
    evidence_text = "【📚 原始片段】\n"
    for i, doc in enumerate(evidences):
        evidence_text += f"> [Ref {i+1}] {doc.page_content[:200]}...\n"

    system_prompt = f"""你是一个专业的知识库助手。
    请基于【调查笔记】和【原始片段】回答用户问题。
    {notes_text}
    {evidence_text}
    严谨引用 [Ref X]。
    """
    
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    
    # 拼接附录供前端显示
    appendix = "\n\n"
    if notes: appendix += "【🕵️‍♂️ 调查笔记】\n" + "\n".join(notes) + "\n\n"
    if evidences:
        appendix += "【📚 原始片段】\n"
        for i, doc in enumerate(evidences):
            appendix += f"> [Ref {i+1}] {doc.page_content[:350]}...\n(Source: {doc.metadata.get('source','Unknown')})\n\n"
    
    response.content += appendix
    return {"messages": [response], "next": "END"}