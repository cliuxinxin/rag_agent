"""LangGraph 节点逻辑实现。"""

import os
import json
from typing import Literal, List
# === 新增 imports ===
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
# ===================
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from src.state import AgentState
from src.bm25 import SimpleBM25Retriever

def get_llm():
    return ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        temperature=0.1
    )

# === 1. Supervisor (总管) ===

class RouteResponse(BaseModel):
    """Supervisor 的决策输出结构"""
    next: Literal["Searcher", "Answerer"] = Field(
        ..., description="下一步交给谁？如果还需要信息选 Searcher，如果信息足够选 Answerer"
    )
    search_query: str = Field(
        default="", description="如果选 Searcher，请填写具体的搜索意图/关键词"
    )
    reasoning: str = Field(
        ..., description="决策理由，简要说明还需要查什么，或者为什么信息已经足够"
    )

def supervisor_node(state: AgentState) -> dict:
    """
    总管节点：分析历史消息，决定下一步行动。
    """
    messages = state["messages"]
    llm = get_llm()
    
    # === 修改开始：使用 PydanticParser 代替 with_structured_output ===
    
    # 1. 创建解析器
    parser = PydanticOutputParser(pydantic_object=RouteResponse)
    
    # 2. 获取格式化指令 (让 LangChain 自动生成 "请输出 JSON..." 的提示词)
    format_instructions = parser.get_format_instructions()

    system_prompt = f"""你是一个严谨的研究项目主管 (Supervisor)。
    你的目标是回答用户的问题。你手下有两个工人：
    1. Searcher: 负责从知识库中检索信息。
    2. Answerer: 当信息充足时，负责生成最终回答。

    请分析【对话历史】。
    - 如果现有的信息（来自 Searcher 的反馈）还不足以回答用户最初的问题，请指派 'Searcher'，并给出具体的搜索指令（search_query）。
    - 如果 Searcher 已经提供了足够的信息，或者尝试多次仍无结果，请指派 'Answerer' 进行总结。
    
    注意：
    - 不要重复搜索相同的关键词。
    - 尽量在 3-4 轮搜索内解决问题。
    
    {format_instructions}
    """
    
    # 3. 普通调用 LLM
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    
    # 4. 手动解析结果
    try:
        # DeepSeek 有时会把 JSON 包裹在 ```json ... ``` 中，Parser 通常能处理
        # 如果处理不了，手动 strip 一下
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "")
        elif content.startswith("```"):
            content = content.replace("```", "")
            
        # 使用解析器转为 Pydantic 对象
        decision = parser.parse(content)
        
    except Exception as e:
        # 兜底策略：如果解析失败，强制转给 Answerer 结束，防止死循环
        print(f"Supervisor 解析错误: {e}, 原始内容: {response.content}")
        decision = RouteResponse(
            next="Answerer", 
            search_query="", 
            reasoning="系统解析错误，转人工处理。"
        )

    # === 修改结束 ===
    
    return {
        "next": decision.next,
        "current_search_query": decision.search_query,
    }

def retrieve(state: AgentState) -> dict:
    """使用 BM25 检索文档。"""
    question = state["question"]
    source_docs = state.get("source_documents", [])

    if not source_docs:
        return {"retrieved_documents": []}

    # 在内存中构建检索器 (针对无向量库场景)
    retriever = SimpleBM25Retriever(source_docs)
    results = retriever.search(question, k=3)  # 每次少取一点，求精
    
    return {"retrieved_documents": results}


def search_node(state: AgentState) -> dict:
    """
    搜索节点：接收 Supervisor 的指令 -> 优化关键词 -> 检索 -> 过滤 -> 返回结果
    """
    query = state.get("current_search_query", "")
    source_docs = state.get("source_documents", [])
    
    if not query or not source_docs:
        return {"messages": [AIMessage(content="Searcher: 没有收到查询指令或知识库为空。", name="Searcher")]}

    # A. 关键词优化 (Keyword Transformation)
    # 自动检测文档主要语言，优化搜索词
    languages = [doc.metadata.get("language", "Chinese") for doc in source_docs]
    target_language = max(set(languages), key=languages.count) if languages else "Chinese"
    
    llm = get_llm()
    trans_msg = [
        SystemMessage(content=f"将用户的搜索意图转换为最适合 BM25 检索的【{target_language}】关键词。直接输出词，不要解释。"),
        HumanMessage(content=query)
    ]
    bm25_query = llm.invoke(trans_msg).content.strip()
    
    # B. 执行检索
    retriever = SimpleBM25Retriever(source_docs)
    # 稍微多取一点，然后用 LLM 过滤
    raw_docs = retriever.search(bm25_query, k=5)
    
    if not raw_docs:
        return {"messages": [AIMessage(content=f"Searcher: 针对 '{query}' (关键词: {bm25_query}) 未找到相关文档。", name="Searcher")]}

    # C. 信息提取与过滤 (阅读理解)
    # 让 LLM 帮我们把文档里的干货提取出来，减少 Supervisor 的阅读负担
    context_text = "\n\n".join([f"[Doc {i}] {d.page_content}" for i, d in enumerate(raw_docs)])
    
    filter_prompt = f"""你是一个搜索结果分析员。
    搜索意图: "{query}"
    原始检索结果:
    {context_text}
    
    请提取出与搜索意图真正相关的信息片段。如果文档不相关，请忽略。
    请以客观陈述的语气汇报发现。保留引用来源 (如 [Doc 0])。
    如果没有有用信息，请回答"无相关信息"。
    """
    
    extraction = llm.invoke([HumanMessage(content=filter_prompt)]).content
    
    # 将结果包装为消息返回给 Supervisor
    result_msg = f"【搜索报告】\n针对指令: '{query}'\n使用的关键词: '{bm25_query}'\n\n发现:\n{extraction}"
    
    return {
        "messages": [AIMessage(content=result_msg, name="Searcher")]
    }

def analyze_and_plan(state: AgentState) -> dict:
    """
    核心节点：阅读文档 -> 提取信息 -> 更新笔记 -> 规划下一步
    """
    original_question = state.get("original_question", state["question"]) # 建议在外部存一个原始问题，或者这里假设 state["question"] 会变
    # 为了简化，我们假设 state["question"] 是当前的搜索词，我们需要一个字段存原始问题。
    # *修正*: 让我们约定 state["question"] 始终是用户原始问题，
    # 而搜索词由 transform_query 临时生成并传给 retrieve，
    # 但由于 retrieve 读取的是 state["question"]，我们需要在 transform 修改 state["question"]。
    # 为了不丢失原始问题，建议在 state 里加一个 origin_question，或者我们这里从 trace[0] 推断。
    # *简单方案*: 我们在 workflow 启动时，把原始问题放入 research_trace 的初始状态。
    
    # 获取当前上下文
    current_docs = state["retrieved_documents"]
    trace = state.get("research_trace", [])
    final_docs = state.get("final_documents", [])
    
    # 获取上一轮的搜索意图
    last_step = trace[-1] if trace else {"query": "Initial Search"}
    current_query = last_step.get("query", "")

    llm = get_llm()

    # --- 1. 并行过滤文档 (保留有效证据) ---
    valid_new_docs = []
    if current_docs:
        # 简单过滤：只要有一点点相关就留着，作为素材
        batch_msgs = [
            [SystemMessage(content="判断文档片段是否包含任何有用的信息。返回JSON: {'relevant': 'yes'/'no'}"),
             HumanMessage(content=f"Doc: {d.page_content[:300]}")]
            for d in current_docs
        ]
        results = llm.batch(batch_msgs)
        for doc, res in zip(current_docs, results):
            if "yes" in res.content.lower():
                if doc.page_content not in [fd.page_content for fd in final_docs]:
                    valid_new_docs.append(doc)
    
    # 更新证据库
    updated_final_docs = final_docs + valid_new_docs
    
    # --- 2. 深度分析与规划 (The Brain) ---
    
    # 构造上下文：把过去的调查结果拼起来
    history_text = ""
    for i, t in enumerate(trace):
        if i == 0: continue # 跳过初始占位
        history_text += f"Step {i}: 搜了 '{t.get('query')}' -> 发现: {t.get('findings')}\n"
    
    # 构造本次检索到的内容文本
    current_docs_text = "\n".join([f"[Doc {i}] {d.page_content}" for i, d in enumerate(valid_new_docs)])
    if not current_docs_text:
        current_docs_text = "本次搜索未找到有效文档。"

    system_prompt = f"""你是一个严谨的研究员。正在通过迭代搜索来回答用户的复杂问题。
    
    【用户原始问题】: {trace[0].get('original_question') if trace else 'Unknown'}
    
    【之前的研究进展】:
    {history_text}
    
    【本次搜索意图】: {current_query}
    
    【本次检索到的新文档】:
    {current_docs_text}
    
    请执行以下思考步骤并输出 JSON：
    1. **Analyze**: 综合【之前的进展】和【新文档】，我们现在知道了什么？本次搜索是否填补了之前的空白？
    2. **Gap Check**: 对照【用户原始问题】，还有哪些关键要素是完全缺失或不确定的？
    3. **Decide**: 
       - 如果信息已经足够回答原始问题，或者多次搜索均无进展，设置 "search_needed": false。
       - 如果还需要补充信息，设置 "search_needed": true。
    4. **Plan**: 如果需要继续搜，请生成下一个具体的搜索建议（next_query）。
    
    JSON 格式示例:
    {{
        "findings_summary": "本次确认了DeepSeek V2支持MoE架构，且总参数量为236B。",
        "missing_info": "仍然缺乏关于具体激活参数量（Active Params）的准确数值。",
        "search_needed": true,
        "next_query": "DeepSeek V2 active parameters count",
        "reasoning": "已知总参数，缺激活参数，需定向查找。"
    }}
    """
    
    try:
        response = llm.invoke([HumanMessage(content=system_prompt)])
        content = response.content.strip().replace("```json", "").replace("```", "")
        analysis = json.loads(content)
    except Exception as e:
        # 兜底
        analysis = {
            "findings_summary": "解析错误或无新发现。",
            "missing_info": "不确定",
            "search_needed": False, # 避免死循环
            "next_query": ""
        }

    # 更新 Trace
    # 我们把本次的分析结果，追加到 trace 中
    # 注意：这里我们把“上一轮的 query”对应的 findings 补全
    if trace:
        trace[-1]["findings"] = analysis["findings_summary"]
        trace[-1]["missing"] = analysis["missing_info"]
    
    # 如果需要继续搜，准备下一条 trace
    if analysis["search_needed"]:
        trace.append({
            "step": len(trace),
            "query": analysis["next_query"], # 这里的 query 还没经过 transform 润色，暂时存建议
            "findings": "Pending...",
            "missing": "Pending..."
        })

    return {
        "final_documents": updated_final_docs,
        "research_trace": trace,
        "search_needed": analysis["search_needed"],
        "retrieved_documents": [] # 清空临时区
    }


def answer_node(state: AgentState) -> dict:
    """
    回答节点：综合所有历史消息，回答用户最初的问题。
    """
    messages = state["messages"]
    llm = get_llm()
    
    # 获取用户最初的问题 (通常是 messages 里的第一个 HumanMessage)
    user_question = "未知问题"
    for m in messages:
        if isinstance(m, HumanMessage):
            user_question = m.content
            break
            
    system_prompt = f"""你是一个专业的知识库助手。
    用户问题: "{user_question}"
    
    请阅读上方的【对话历史】，其中包含了 Supervisor 的调度记录和 Searcher 的搜索报告。
    请综合这些信息，给出最终的详尽回答。
    如果搜索结果仍无法完全回答问题，请诚实说明缺少的环节。
    """
    
    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)
    
    # 返回最终回答
    return {
        "messages": [response],
        "next": "END" # 标记结束
    }

def transform_query(state: AgentState) -> dict:
    """
    执行规划：取出 Trace 中的 'next_query' 建议，进行 BM25 格式化/翻译。
    """
    trace = state.get("research_trace", [])
    source_docs = state.get("source_documents", [])
    
    # 获取最新的计划
    if not trace:
        # 极少情况，初始化
        raw_query = state["question"]
        # 初始化 trace
        trace = [{"step": 0, "original_question": raw_query, "query": raw_query, "findings": "Start", "missing": "All"}]
    else:
        # 取出 analyze_and_plan 生成的建议
        raw_query = trace[-1].get("query", state["question"])

    # 语言优化逻辑 (复用之前的)
    languages = [doc.metadata.get("language", "Chinese") for doc in source_docs]
    target_language = max(set(languages), key=languages.count) if languages else "Chinese"
    
    llm = get_llm()
    msg = [
        SystemMessage(content=f"""你是一个搜索关键词优化助手。
        目标语言：【{target_language}】。
        用户的搜索意图是："{raw_query}"。
        请将其转换为最适合 BM25 倒排索引检索的关键词字符串。
        不要解释，只输出字符串。"""),
        HumanMessage(content="Convert this query.")
    ]
    
    bm25_query = llm.invoke(msg).content
    
    # 关键点：我们需要把优化后的词写回 trace，或者更新 state["question"] 供 retrieve 使用
    # 这里我们更新 state["question"] 供 retrieve 用
    # 同时更新 trace 里的 query 为实际执行的词（可选）
    
    return {
        "question": bm25_query, 
        "research_trace": trace,
        "search_count": state.get("search_count", 0) + 1
    }


def generate(state: AgentState) -> dict:
    """
    最终生成：基于完整的调查笔记 (Research Trace) 和 证据 (Final Docs) 回答。
    """
    trace = state.get("research_trace", [])
    final_docs = state.get("final_documents", [])
    original_question = trace[0].get("original_question") if trace else state["question"]
    
    llm = get_llm()
    
    # 构造"调查报告"
    report = "【调查过程记录】\n"
    for t in trace:
        if t.get("step") == 0: continue
        report += f"- 步骤 {t.get('step')}: 搜索了 '{t.get('query')}'\n"
        report += f"  发现: {t.get('findings')}\n"
        report += f"  遗留问题: {t.get('missing')}\n"
    
    # 构造证据引用
    evidence = "\n\n".join([f"[Ref {i+1}] {d.page_content}" for i, d in enumerate(final_docs)])
    
    prompt = f"""你是一个智能知识库助手。请根据以下的【调查过程记录】和【参考文档证据】，回答用户的最终问题。
    
    用户问题: {original_question}
    
    ----------------
    {report}
    ----------------
    
    参考文档证据:
    {evidence}
    
    ----------------
    请按照以下逻辑回答：
    1. 先总结你的调查思路（例如："我先查找了A，确认了X，然后针对Y进行了补充搜索..."）。
    2. 给出详细的最终答案。
    3. 如果仍有无法确认的信息，请诚实说明。
    """
    
    response = llm.invoke(prompt)
    return {"generation": response.content}
