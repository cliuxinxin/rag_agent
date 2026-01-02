# src/nodes/chat_nodes.py
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from src.state import AgentState
from src.nodes.common import get_llm
from src.logger import get_logger
from src.bm25 import SimpleBM25Retriever
from src.storage import peek_kb_random_chunks

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
    kb_names = state.get("kb_names", [])
    # 获取当前的动态画像
    current_summary = state.get("kb_summary", "未知领域")
    
    # [Log] 记录搜索动作
    logger.info(f"[Searcher] 开始执行搜索任务: '{query}' | 当前对库的理解: {current_summary}")
    
    if not query:
        logger.warning("[Searcher] 收到空查询指令")
        return {"messages": [AIMessage(content="Searcher: 指令为空。", name="Searcher")]}

    llm = get_llm()

    # === 1. [核心通用逻辑] 获取样本 ===
    # 无论 current_summary 是否为空，都获取样本，增强 Prompt 的"体感"
    # 这步操作非常快（毫秒级），不会影响性能
    kb_preview_text = peek_kb_random_chunks(kb_names, sample_size=3)
    
    logger.info(f"[Searcher] 正在基于采样内容生成关键词...")

    # === 2. 通用型 Prompt：不预设任何立场，只做"翻译" ===
    # 结合采样和 summary（如果有的话），双重优化
    summary_context = ""
    if current_summary and len(current_summary) > 10 and "未知" not in current_summary and "暂时未知" not in current_summary:
        summary_context = f"\n【补充：我们之前了解到这个知识库】{current_summary}\n"
    
    expansion_prompt = f"""你是一个专业的"术语对齐"专家。

【任务】
用户想搜索："{query}"

【知识库实地采样】
(以下是从数据库中随机抽取的 3 个片段，请仔细观察其**年代、语体、专业术语**)
--- 采样开始 ---
{kb_preview_text}
--- 采样结束 ---
{summary_context}
【指令】
1. 请模仿【知识库采样】的行文风格和用词习惯。
2. 将用户的搜索意图**翻译**成最可能出现在该数据库中的 3-4 个关键词。
3. **严禁使用现代词汇**，除非采样中出现了现代词汇。
   - 如果采样是古文，就用古文词。
   - 如果采样是代码，就用类名、函数名。

请直接输出关键词，用空格分隔："""
    
    try:
        bm25_keywords = llm.invoke([HumanMessage(content=expansion_prompt)]).content.strip().replace('"', '').replace('\n', ' ')
        logger.info(f"[Searcher] 采样对齐后的关键词: {bm25_keywords}")
    except Exception as e:
        logger.error(f"[Searcher] 关键词生成失败: {e}")
        bm25_keywords = query
    
    results_bm25 = []
    results_vector = []

    if source_docs:
        try:
            bm25_retriever = SimpleBM25Retriever(source_docs)
            results_bm25 = bm25_retriever.search(f"{query} {bm25_keywords}", k=10)
        except Exception as e:
            logger.warning(f"BM25 检索失败: {e}")
            results_bm25 = []
    
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
            "failed_topics": [query],
            "kb_summary": current_summary  # 保持原有画像
        }

    # === 3. [核心新增] 动态更新知识库画像 (Learn from Docs) ===
    new_summary = current_summary
    if final_docs:
        # 提取这次检索到的内容的摘要
        content_preview = "\n".join([d.page_content[:200] for d in final_docs[:3]])
        
        update_profile_prompt = f"""我们要维护一个"知识库画像"，通过阅读检索到的片段来不断修正我们对这个知识库的认知。

【旧画像】{current_summary}
【新检索到的片段】
{content_preview}

请结合【新片段】，用一句话更新【旧画像】。
描述这个知识库主要是关于什么领域的？包含哪些核心技术栈或业务？
不要太长，只保留核心特征。"""
        
        # 这是一个后台"学习"过程，不应该阻塞太久，但为了效果我们同步执行
        try:
            new_summary = llm.invoke([HumanMessage(content=update_profile_prompt)]).content.strip()
            logger.info(f"[Learning] 知识库画像已更新: {new_summary}")
        except Exception as e:
            logger.error(f"[Learning] 画像更新失败: {e}")
            new_summary = current_summary

    # === 4. 生成笔记 (保持原有逻辑) ===
    context_text = "\n\n".join([f"[Ref {i+1}] {d.page_content}" for i, d in enumerate(final_docs)])
    filter_prompt = f"任务: '{query}'\n资料:\n{context_text}\n请提取关键信息。"
    extraction = llm.invoke([HumanMessage(content=filter_prompt)]).content
    
    current_note = f"### 🔍 搜索主题: {query} (关键词: {bm25_keywords})\n{extraction}\n"
    
    logger.info(f"[Searcher] 笔记提取完成，准备返回。")

    return {
        "messages": [AIMessage(content=f"【搜索报告】\n方向: {query}\n发现:\n{extraction}", name="Searcher")],
        "final_evidence": final_docs,
        "attempted_searches": [query],
        "research_notes": [current_note],
        # [新增] 将更新后的画像回写到状态中，供下一轮使用
        "kb_summary": new_summary
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