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

# 引入 FlashRank
try:
    from flashrank import Ranker, RerankRequest
    # 确保缓存目录存在
    os.makedirs("opt", exist_ok=True)
    reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="opt")
    USE_RERANKER = True
except ImportError:
    USE_RERANKER = False
    print("未安装 flashrank，将跳过重排序步骤。")
except Exception as e:
    USE_RERANKER = False
    print(f"FlashRank 初始化失败: {e}")

def get_llm():
    return ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        temperature=0.3,
        max_retries=2
    )

# === 1. Supervisor ===

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
    
    # 变量定义防报错
    if past_searches:
        history_str = "\n".join([f"- {q}" for q in past_searches])
    else:
        history_str = "无"

    if failed_topics:
        failed_str = "\n".join([f"- {q}" for q in failed_topics])
    else:
        failed_str = "无"

    if current_loop >= MAX_LOOPS:
        return {"next": "Answerer", "current_search_query": "", "loop_count": current_loop}

    parser = PydanticOutputParser(pydantic_object=RouteResponse)
    format_instructions = parser.get_format_instructions()

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
       - 如果 Searcher 已经提供了推断的标题或核心信息，请不要再重复要求确认标题，直接基于该信息进行深入挖掘。
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
        decision = RouteResponse(
            observed_gap="Error", next="Answerer", search_query="", reasoning="System Error"
        )

    print(f"\n🤔 [Supervisor Loop {current_loop + 1}]\n决定: {decision.next} -> {decision.search_query}\n")

    return {
        "next": decision.next,
        "current_search_query": decision.search_query,
        "loop_count": current_loop + 1
    }

# === 2. Searcher ===

def search_node(state: AgentState) -> dict:
    query = state.get("current_search_query", "")
    source_docs = state.get("source_documents", [])
    vector_store = state.get("vector_store", None)
    
    if not query:
        return {"messages": [AIMessage(content="Searcher: 指令为空。", name="Searcher")]}

    llm = get_llm()

    # 关键词扩展
    expansion_prompt = f"""你是一个搜索专家。请针对搜索意图 "{query}"，生成 3-4 个用于关键词检索的扩展词。
    【特殊策略】：
    - **概括性问题**：如果用户问“这篇文章讲了什么”、“总结”、“主要内容”，请务必包含：
      "Abstract", "Introduction", "Conclusion", "Summary", "Table of Contents", "Overview", "摘要", "结论", "目录"。
    - **细节问题**：提取核心实体。
    只输出关键词，用空格分隔。"""
    
    bm25_keywords = llm.invoke([HumanMessage(content=expansion_prompt)]).content.strip().replace('"', '')
    
    results_bm25 = []
    results_vector = []

    # 检索
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
    unique_docs_list = list(unique_docs.values())

    if not unique_docs_list:
        return {
            "messages": [AIMessage(content=f"Searcher: 未找到相关信息。", name="Searcher")],
            "attempted_searches": [query],
            "failed_topics": [query]
        }

    # 重排序
    if USE_RERANKER:
        try:
            passages = [
                {"id": i, "text": doc.page_content, "meta": doc.metadata} 
                for i, doc in enumerate(unique_docs_list)
            ]
            rerank_request = RerankRequest(query=query, passages=passages)
            reranked_results = reranker.rank(rerank_request)
            
            final_docs = []
            for item in reranked_results[:6]:
                doc = Document(page_content=item['text'], metadata=item['meta'])
                final_docs.append(doc)
        except Exception as e:
            print(f"Rerank Error: {e}")
            final_docs = unique_docs_list[:6]
    else:
        final_docs = unique_docs_list[:6]

    # 笔记生成
    context_text = "\n\n".join([f"[Ref {i+1}] {d.page_content}" for i, d in enumerate(final_docs)])
    filter_prompt = f"""你是一个情报分析员。
    任务: "{query}"
    资料:
    {context_text}
    请提取关键信息。如果是概括性问题，重点提取结构和结论。"""
    extraction = llm.invoke([HumanMessage(content=filter_prompt)]).content
    
    current_note = f"### 🔍 搜索主题: {query} (关键词: {bm25_keywords})\n{extraction}\n"

    return {
        "messages": [AIMessage(content=f"【搜索报告】\n方向: {query}\n发现:\n{extraction}", name="Searcher")],
        "final_evidence": final_docs,
        "attempted_searches": [query],
        "research_notes": [current_note]
    }

# === 3. Answerer (核心修改：强制拼接附录) ===

def answer_node(state: AgentState) -> dict:
    messages = state["messages"]
    evidences = state.get("final_evidence", [])
    notes = state.get("research_notes", [])
    
    llm = get_llm()
    
    # 构造 Prompt 用的上下文
    notes_text = "【🕵️‍♂️ 调查笔记】\n" + "\n".join(notes) if notes else "无调查记录。"
    evidence_text = "【📚 原始片段】\n"
    for i, doc in enumerate(evidences):
        content_preview = doc.page_content.replace('\n', ' ')[:200]
        evidence_text += f"> [Ref {i+1}] {content_preview}...\n"

    system_prompt = f"""你是一个专业的知识库助手。
    请基于【调查笔记】和【原始片段】回答用户问题。
    
    {notes_text}
    {evidence_text}
    
    【撰写要求】
    1. 结构清晰：核心结论 -> 过程综述 -> 详细分析。
    2. 严谨引用：文中必须引用 [Ref X]。
    3. 建议进一步挖掘的问题：恰好 3 个，必须基于知识库，不要问公网问题。
    """
    
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    
    # === 核心修复：将详细数据拼接到回复末尾 ===
    # 这一步至关重要，因为 LLM 通常不会自己把原始文档抄一遍返回。
    # 我们必须手动 append，前端才能提取到内容用于 Tooltip 和 Expander。
    
    appendix = "\n\n"
    
    if notes:
        appendix += "【🕵️‍♂️ 调查笔记】\n" + "\n".join(notes) + "\n\n"
    
    if evidences:
        appendix += "【📚 原始片段】\n"
        for i, doc in enumerate(evidences):
            # 清理换行符，保持整洁
            content = doc.page_content.replace('\n', ' ')[:350] # 截取前350字符，防止过长
            source = doc.metadata.get('source', 'Unknown')
            # 格式必须严格符合前端正则: > [Ref ID] Content...
            appendix += f"> [Ref {i+1}] {content}...\n(Source: {source})\n\n"
    
    # 修改消息内容
    response.content += appendix
    
    return {"messages": [response], "next": "END"}