"""LangGraph 节点逻辑实现。"""

import os
import json
from typing import Literal
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from src.state import AgentState

# 引入 FlashRank (如果你之前装了)
try:
    from flashrank import Ranker, RerankRequest
    # 使用轻量级模型
    reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="opt")
    USE_RERANKER = True
except ImportError:
    USE_RERANKER = False
    print("未安装 flashrank，将跳过重排序步骤。")

def get_llm():
    return ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        temperature=0.3,
        max_retries=2
    )

# === 1. Supervisor (通用研究主管) ===

class RouteResponse(BaseModel):
    """Supervisor 决策结构"""
    observed_gap: str = Field(
        ..., 
        description="分析当前信息与用户问题之间的差距。我们还缺什么信息才能完美回答？"
    )
    next: Literal["Searcher", "Answerer"] = Field(
        ..., description="如果信息有缺口选 Searcher，信息充足选 Answerer。"
    )
    search_query: str = Field(
        default="", description="针对【observed_gap】生成的下一步具体搜索指令。"
    )
    reasoning: str = Field(
        ..., description="决策理由。"
    )

def supervisor_node(state: AgentState) -> dict:
    messages = state["messages"]
    current_loop = state.get("loop_count", 0)
    
    # === 1. 优先获取状态值 ===
    past_searches = state.get("attempted_searches", [])
    failed_topics = state.get("failed_topics", [])
    
    MAX_LOOPS = 6 
    llm = get_llm()
    
    # === 2. 无论如何，先定义好字符串变量 ===
    # 避免 "UnboundLocalError" 的关键：在使用前确保赋值
    if past_searches:
        history_str = "\n".join([f"- {q}" for q in past_searches])
    else:
        history_str = "无"

    if failed_topics:
        failed_str = "\n".join([f"- {q}" for q in failed_topics])
    else:
        failed_str = "无"

    # === 3. 循环限制检查 ===
    if current_loop >= MAX_LOOPS:
        return {"next": "Answerer", "current_search_query": "", "loop_count": current_loop}

    parser = PydanticOutputParser(pydantic_object=RouteResponse)
    format_instructions = parser.get_format_instructions()

    # === 4. 构造 Prompt (此时变量一定有值) ===
    system_prompt = f"""你是一个全能型的研究项目主管。
    当前研究轮次：{current_loop + 1} / {MAX_LOOPS}。
    
    【已尝试的搜索】
    {history_str}
    
    【❌ 已确认无结果的话题 (不要重搜)】
    {failed_str}
    
    【工作流程】
    1. 分析现状：我们知道了什么？
    2. **识别缺口**：
       - 如果用户问“这篇文章讲了什么/总结全文”，且我们还没搜过“摘要/目录”，这是巨大缺口。
       - 如果是细节问题，检查是否缺少关键数据。
    3. **智能决策**：
       - 如果 Searcher 已经提供了推断的标题或核心信息，请不要再重复要求确认标题，直接基于该信息进行深入挖掘（如架构、实验结果）。
       - 一旦识别出可能的论文标题或核心主题，立刻转向内容深挖，不要纠结于元数据（Metadata）的确认。
    4. 决策：指派 Searcher 或 Answerer。
    
    {format_instructions}
    """
    
    try:
        response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "")
        elif content.startswith("```"):
            content = content.replace("```", "")
        decision = parser.parse(content)
    except Exception as e:
        print(f"Supervisor Error: {e}")
        # 兜底
        decision = RouteResponse(
            observed_gap="Error", next="Answerer", search_query="", reasoning="System Error"
        )

    print(f"\n🤔 [Supervisor Loop {current_loop + 1}]\n决定: {decision.next} -> {decision.search_query}\n")

    return {
        "next": decision.next,
        "current_search_query": decision.search_query,
        "loop_count": current_loop + 1
    }

# === 2. Searcher (通用情报搜集员) ===

def search_node(state: AgentState) -> dict:
    query = state.get("current_search_query", "")
    source_docs = state.get("source_documents", [])
    vector_store = state.get("vector_store", None)
    
    if not query:
        return {"messages": [AIMessage(content="Searcher: 指令为空。", name="Searcher")]}

    llm = get_llm()

    # === 1. 关键词扩展 (针对概括性问题优化) ===
    expansion_prompt = f"""你是一个搜索专家。请针对搜索意图 "{query}"，生成 3-4 个用于关键词检索的扩展词。
    
    【特殊策略】：
    - **概括性问题**：如果用户问“这篇文章讲了什么”、“总结”、“主要内容”，请务必包含：
      "Abstract", "Introduction", "Conclusion", "Summary", "Table of Contents", "Overview", "摘要", "结论", "目录"。
    - **细节问题**：提取核心实体、同义词、专业术语。
    
    只输出关键词字符串，用空格分隔。不要解释。"""
    
    bm25_keywords = llm.invoke([HumanMessage(content=expansion_prompt)]).content.strip().replace('"', '')
    
    results_bm25 = []
    results_vector = []

    # 2. 检索 (稍微扩大召回，防止漏掉首尾)
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

    # 3. 合并去重
    all_results = results_vector + results_bm25
    unique_docs = {}
    for doc in all_results:
        if doc.page_content not in unique_docs:
            unique_docs[doc.page_content] = doc
    unique_docs_list = list(unique_docs.values())

    if not unique_docs_list:
        return {
            "messages": [AIMessage(content=f"Searcher: 未找到相关信息。", name="Searcher")],
            "attempted_searches": [query],
            "failed_topics": [query]
        }

    # 4. 重排序 (Rerank)
    if USE_RERANKER:
        try:
            passages = [
                {"id": i, "text": doc.page_content, "meta": doc.metadata} 
                for i, doc in enumerate(unique_docs_list)
            ]
            rerank_request = RerankRequest(query=query, passages=passages)
            reranked_results = reranker.rank(rerank_request)
            
            final_docs = []
            for item in reranked_results[:6]: # 取前6个
                doc = Document(page_content=item['text'], metadata=item['meta'])
                final_docs.append(doc)
        except Exception as e:
            print(f"Rerank Error: {e}")
            final_docs = unique_docs_list[:6]
    else:
        final_docs = unique_docs_list[:6]

    # 5. 信息萃取 (笔记生成)
    context_text = "\n\n".join([f"[Ref {i+1}] {d.page_content}" for i, d in enumerate(final_docs)])
    
    filter_prompt = f"""你是一个情报分析员。
    任务: "{query}"
    资料:
    {context_text}
    
    请提取关键信息（定义、数据、核心观点）。
    如果是概括性问题，请重点提取文章结构、主要结论。
    """
    extraction = llm.invoke([HumanMessage(content=filter_prompt)]).content
    
    current_note = f"### 🔍 搜索主题: {query} (关键词: {bm25_keywords})\n{extraction}\n"

    return {
        "messages": [AIMessage(content=f"【搜索报告】\n方向: {query}\n发现:\n{extraction}", name="Searcher")],
        "final_evidence": final_docs,
        "attempted_searches": [query],
        "research_notes": [current_note]
    }

# === 3. Answerer (通用内容创作者) ===

def answer_node(state: AgentState) -> dict:
    messages = state["messages"]
    evidences = state.get("final_evidence", [])
    notes = state.get("research_notes", [])
    
    llm = get_llm()
    
    # 1. 构造笔记本内容
    notes_text = ""
    if notes:
        notes_text = "【🕵️‍♂️ 调查笔记】\n" + "\n".join(notes)
    else:
        notes_text = "无调查记录。"
    
    # 2. 构造原始证据
    evidence_text = ""
    if evidences:
        evidence_text = "【📚 原始片段】\n"
        for i, doc in enumerate(evidences):
            content_preview = doc.page_content.replace('\n', ' ')[:200]
            evidence_text += f"> [Ref {i+1}] {content_preview}...\n"
    
    system_prompt = f"""你是一个专业的知识库助手。
    请基于【调查笔记】和【原始片段】回答用户问题。
    
    {notes_text}
    
    {evidence_text}
    
    【撰写要求】
    1. **结构清晰**：核心结论 -> 过程综述 -> 详细分析。
    2. **概括能力**：如果用户问“讲了什么”，请串联各个片段的要点，形成连贯的摘要，而不是碎片化的列举。
    3. **严谨引用**：引用 [Ref X]。
    4. **⚖️ 盲点与局限**：诚实列出未找到的信息。
    
    5. **🧐 建议进一步挖掘的问题 (Strictly 3 Questions)**：
       - 请生成 **恰好 3 个** 后续问题。
       - **关键约束**：这些问题必须是**基于当前知识库内容**的延伸。
       - **禁止**：不要问需要去公网搜索才能回答的问题（如“未来的发展趋势”、“最新新闻”），除非知识库里提到了。
       - 格式：
         1. [点击] 问题内容
         2. [点击] 问题内容
         3. [点击] 问题内容
    """
    
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    return {"messages": [response], "next": "END"}