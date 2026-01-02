# src/nodes/chat_nodes.py
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from src.state import AgentState
from src.nodes.common import get_llm
from src.logger import get_logger

# 获取 logger 实例
logger = get_logger("Node_Chat")

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
    
    # [Log] 记录进入节点
    logger.info(f"======== [Supervisor] 进入第 {current_loop} 轮思考 ========")
    
    MAX_LOOPS = 6 
    llm = get_llm()
    
    history_str = "\n".join([f"- {q}" for q in past_searches]) if past_searches else "无"
    failed_str = "\n".join([f"- {q}" for q in failed_topics]) if failed_topics else "无"

    if current_loop >= MAX_LOOPS:
        logger.warning(f"[Supervisor] 达到最大循环次数 {MAX_LOOPS}，强制结束。")
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
        
        # [Log] 关键决策日志
        logger.info(f"[Supervisor] 决策: {decision.next} | 理由: {decision.reasoning[:50]}...")
        if decision.next == "Searcher":
            logger.info(f"[Supervisor] 指派搜索词: '{decision.search_query}'")
            
    except Exception as e:
        logger.error(f"[Supervisor] 解析错误或 LLM 异常: {e}", exc_info=True)
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
    
    # [Log] 记录搜索动作
    logger.info(f"[Searcher] 开始执行搜索任务: '{query}'")
    
    if not query:
        logger.warning("[Searcher] 收到空查询指令")
        return {"messages": [AIMessage(content="Searcher: 指令为空。", name="Searcher")]}

    llm = get_llm()

    # 简单扩充关键词
    expansion_prompt = f"针对搜索意图 '{query}'，生成 3-4 个关键词，空格分隔。"
    try:
        bm25_keywords = llm.invoke([HumanMessage(content=expansion_prompt)]).content.strip().replace('"', '')
        logger.info(f"[Searcher] 扩展关键词: {bm25_keywords}")
    except Exception as e:
        logger.error(f"[Searcher] 关键词扩展失败: {e}")
        bm25_keywords = query
    
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
    
    logger.info(f"[Searcher] 检索完成，找到 {len(final_docs)} 条相关片段")

    if not final_docs:
        logger.warning(f"[Searcher] 未找到相关信息，查询: '{query}'")
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
    
    logger.info(f"[Searcher] 笔记提取完成，准备返回。")

    return {
        "messages": [AIMessage(content=f"【搜索报告】\n方向: {query}\n发现:\n{extraction}", name="Searcher")],
        "final_evidence": final_docs,
        "attempted_searches": [query],
        "research_notes": [current_note]
    }

# === Answerer ===

def answer_node(state: AgentState) -> dict:
    logger.info("[Answerer] 开始生成最终回答...")
    
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
    
    try:
        response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
        
        logger.info(f"[Answerer] 回答生成完毕 (长度: {len(response.content)})")
    except Exception as e:
        logger.error(f"[Answerer] 生成回答失败: {e}", exc_info=True)
        raise e
    
    # 拼接附录供前端显示
    appendix = "\n\n"
    if notes: appendix += "【🕵️‍♂️ 调查笔记】\n" + "\n".join(notes) + "\n\n"
    if evidences:
        appendix += "【📚 原始片段】\n"
        for i, doc in enumerate(evidences):
            appendix += f"> [Ref {i+1}] {doc.page_content[:350]}...\n(Source: {doc.metadata.get('source','Unknown')})\n\n"
    
    response.content += appendix
    return {"messages": [response], "next": "END"}