"""LangGraph 节点逻辑实现。"""

import os
import json
from typing import Literal
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.retrievers import BM25Retriever
from src.state import AgentState

def get_llm():
    # 建议调高一点 temperature，让通用回答稍微灵活一点，但不要太高
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
    # 获取当前轮次，默认为0
    current_loop = state.get("loop_count", 0)
    # === 获取记忆 ===
    past_searches = state.get("attempted_searches", [])
    failed_topics = state.get("failed_topics", [])
    # 设置最大搜索深度，建议 5-8 次
    MAX_LOOPS = 6 

    llm = get_llm()
    
    # === 强制止损逻辑 ===
    if current_loop >= MAX_LOOPS:
        print(f"🛑 达到最大循环次数 ({MAX_LOOPS})，强制转 Answerer。")
        return {
            "next": "Answerer",
            "current_search_query": "",
            "loop_count": current_loop  # 保持不变
        }

    parser = PydanticOutputParser(pydantic_object=RouteResponse)
    format_instructions = parser.get_format_instructions()

    # === 构造记忆文本 ===
    # 将列表格式化为字符串，放入 Prompt
    if past_searches:
        history_str = "\n".join([f"- {q}" for q in past_searches])
    else:
        history_str = "无 (这是第一次搜索)"
        
    # === 构造失败话题文本 ===
    if failed_topics:
        failed_str = "\n".join([f"- {q}" for q in failed_topics])
        failed_section = f"""【❌ 已确认知识库中缺失的话题 (不要再搜！)】
{failed_str}"""
    else:
        failed_section = "无"

    system_prompt = f"""你是一个全能型的研究项目主管。
    当前研究轮次：{current_loop + 1} / {MAX_LOOPS}。
    
    【🚫 已尝试的搜索路径 (绝对禁止重复语义)】
    {history_str}
    
    {failed_section}
    
    【工作流程】
    1. **分析现状**：阅读历史搜索报告。用户问了什么？我们现在知道了什么？
    2. **识别缺口 (Gap Analysis)**：
       - 是否还有未解释的**专有名词**？
       - 是否只找到了A面，而忽略了**B面**（如只看了优点没看缺点）？
       - 是否还需要具体的**数据/案例**来支撑论点？
    3. **决策**：
       - 如果存在关键缺口，指派 'Searcher' 进行针对性挖掘。
       - 如果信息已足够形成一个逻辑严密的回答，或多次搜索无果，指派 'Answerer'。
       - 如果缺口涉及【❌ 缺失话题】，请直接忽略该部分，不要再指派 Searcher 去搜这些死路。
    
    【重要】你还有 {MAX_LOOPS - current_loop} 次搜索机会。请珍惜次数，尽量精准。
    
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

    print(f"\n🤔 [Supervisor Loop {current_loop + 1}]\n已搜过: {past_searches}\n失败话题: {failed_topics}\n决定: {decision.next} -> {decision.search_query}\n")

    return {
        "next": decision.next,
        "current_search_query": decision.search_query,
        # 每次经过 Supervisor，计数器 +1
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

    # A. 关键词泛化 (Keyword Expansion)
    # 不再强制加 "root cause"，而是根据语义扩展
    expansion_prompt = f"""你是一个搜索专家。请针对搜索意图 "{query}"，生成 2-3 个用于关键词检索的扩展词。
    策略：
    1. 提取核心实体（Entity）。
    2. 补充同义词、专业术语或英文翻译。
    3. 如果是特定领域（如法律、医疗），加入相关限定词。
    
    只输出关键词，用空格分隔。"""
    
    bm25_keywords = llm.invoke([HumanMessage(content=expansion_prompt)]).content.strip().replace('"', '')
    
    results_bm25 = []
    results_vector = []

    # B. 混合检索执行
    if source_docs:
        try:
            bm25_retriever = BM25Retriever.from_documents(source_docs)
            bm25_retriever.k = 3
            # 组合查询：自然语言 + 扩展关键词
            results_bm25 = bm25_retriever.invoke(f"{query} {bm25_keywords}")
        except: pass
    
    if vector_store:
        try:
            vector_retriever = vector_store.as_retriever(search_kwargs={"k": 4}) # 向量多取一点
            results_vector = vector_retriever.invoke(query)
        except: pass

    # C. 结果合并与去重
    all_results = results_vector + results_bm25
    unique_docs = []
    seen = set()
    for doc in all_results:
        if doc.page_content not in seen:
            unique_docs.append(doc)
            seen.add(doc.page_content)
    
    final_docs = unique_docs[:6] # 稍微多给一点上下文
    
    if not final_docs:
        return {
            "messages": [AIMessage(content=f"Searcher: 未找到关于 '{query}' 的相关信息。", name="Searcher")],
            # 即使没找到，也要记录“我搜过这个词了”，防止 Supervisor 又让搜一遍
            "attempted_searches": [query],
            # === 标记为失败话题 ===
            "failed_topics": [query]
        }

    # D. 信息萃取 (通用化)
    context_text = "\n\n".join([f"[Ref {i+1}] {d.page_content}" for i, d in enumerate(final_docs)])
    
    filter_prompt = f"""你是一个客观的情报分析员。
    
    【搜索任务】: "{query}"
    【检索资料】:
    {context_text}
    
    请从资料中提取与任务相关的信息。
    要求：
    1. 保持客观，不要编造。
    2. 提取关键定义、数据、观点、时间线或因果关系。
    3. 如果资料包含矛盾信息，请一并列出。
    4. 如果资料中完全没有与搜索任务相关的内容，请明确说明"未找到相关内容"。
    """
    
    extraction = llm.invoke([HumanMessage(content=filter_prompt)]).content
    
    # === 新增：检查是否真的找到了相关内容 ===
    # 如果LLM明确表示未找到相关内容，则标记为失败话题
    is_empty_result = "未找到" in extraction or "没有找到" in extraction or "无相关" in extraction
    
    if is_empty_result:
        return {
            "messages": [AIMessage(content=f"【搜索报告】\n检索方向: {query}\n扩展词: {bm25_keywords}\n发现:\n{extraction}", name="Searcher")],
            "attempted_searches": [query],
            # === 标记为失败话题 ===
            "failed_topics": [query]
        }
    
    return {
        "messages": [AIMessage(content=f"【搜索报告】\n检索方向: {query}\n扩展词: {bm25_keywords}\n发现:\n{extraction}", name="Searcher")],
        "final_evidence": final_docs,
        
        # === 核心修改：将当前 Query 写入记忆 ===
        # 由于 State 定义了 operator.add，这个列表会被追加到总列表中
        "attempted_searches": [query]
    }

# === 3. Answerer (通用内容创作者) ===

def answer_node(state: AgentState) -> dict:
    messages = state["messages"]
    evidences = state.get("final_evidence", [])
    
    llm = get_llm()
    
    evidence_text = ""
    if evidences:
        evidence_text = "【原始知识库片段】\n"
        for i, doc in enumerate(evidences):
            content_preview = doc.page_content.replace('\n', ' ')[:300] # 限制长度防止 token 溢出
            evidence_text += f"> [Ref {i+1}] ...{content_preview}...\n(Source: {doc.metadata.get('source', 'Unknown')})\n\n"
    else:
        evidence_text = "【原始知识库片段】: 无\n"
        
    system_prompt = f"""你是一个专业的知识整合专家。
    
    请基于【AI回答历史】和【原始知识库片段】回答用户问题。
    
    {evidence_text}
    
    【输出结构要求】
    1. **深度回答**：详细回答用户问题，引用 [Ref X] 佐证。
    2. **结论**：一句话总结核心观点。
    3. **🧐 建议进一步研究的问题**：
       - 基于现有的回答，生成 3 个用户可能感兴趣的**深层问题**。
       - 这些问题应该能引导用户挖掘文档中尚未充分展开的细节。
    """
    
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    return {"messages": [response], "next": "END"}