import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes import get_llm
from src.storage import load_kbs
from langchain_community.retrievers import BM25Retriever

# ==========================================
# PART 1: 智能调研与大纲生成 (Agent Loop)
# ==========================================

# 1. 写作规划师 (Planner): 决定还需要调研什么
def write_planner_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    qa_history = state.get("qa_pairs", [])
    loop = state.get("loop_count", 0)
    MAX_LOOPS = 3  # 写作调研不用太深，3轮足够梳理结构
    
    llm = get_llm()
    history_text = "\n".join(qa_history) if qa_history else "（暂无，第一轮）"
    
    prompt = f"""
    你是写作筹备组的组长。
    【写作任务】{req}
    【已获取的信息】
    {history_text}
    
    当前轮次: {loop + 1}/{MAX_LOOPS}
    
    请判断：为了写出一份高质量的【调研报告】和【文章大纲】，我们还需要查证什么关键信息？
    - 比如：核心概念的定义、具体的案例、正反面观点等。
    - 如果信息已经足够构建大纲，请输出 "TERMINATE"。
    - 否则，输出一个具体的【调研问题】。
    """
    
    response = llm.invoke([HumanMessage(content=prompt)]).content.strip().replace('"', '')
    
    if "TERMINATE" in response or loop >= MAX_LOOPS:
        return {"next": "ReportGenerator"}
    else:
        return {"next": "Researcher", "current_question": response, "loop_count": loop + 1}

# 2. 调研员 (Researcher): 查知识库
def write_researcher_node(state: WriterState) -> dict:
    query = state["current_question"]
    kb_names = state.get("kb_names", [])
    source_content = state.get("source_content", "")
    
    llm = get_llm()
    context = ""
    
    # 简单的混合检索策略
    if kb_names:
        docs, _ = load_kbs(kb_names)
        if docs:
            retriever = BM25Retriever.from_documents(docs)
            retriever.k = 5
            results = retriever.invoke(query)
            context += "\n【KB Ref】\n" + "\n".join([d.page_content[:400] for d in results])
    
    if source_content:
        # 如果有上传全文，这里简单处理，实际可做更复杂的切片检索
        context += f"\n【Upload Content】\n{source_content[:2000]}..." 
        
    # 让 LLM 回答问题
    prompt = f"""
    问题：{query}
    资料：{context}
    请简练回答问题，提取关键素材。
    """
    answer = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {
        "qa_pairs": [f"Q: {query}\nA: {answer}"],
        "next": "Planner"
    }

# 3. 报告生成器 (ReportGenerator): 汇总 QA 生成调研报告
def report_generator_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    qa_history = state.get("qa_pairs", [])
    
    llm = get_llm()
    history_text = "\n\n".join(qa_history)
    
    prompt = f"""
    请基于以下调研过程，写一份【文章策划与调研报告】。
    
    【任务】{req}
    【调研素材】
    {history_text}
    
    【报告要求】
    1. **核心立意**：一句话概括文章中心思想。
    2. **目标读者画像**。
    3. **关键素材清单**：列出我们准备用到的核心数据、案例或观点。
    4. **风格基调**。
    
    请直接输出 Markdown 格式。
    """
    
    report = llm.invoke([HumanMessage(content=prompt)]).content
    return {"research_report": report, "next": "OutlineGenerator"}

# 4. 大纲生成器 (OutlineGenerator): 基于报告生成大纲
def outline_generator_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    report = state["research_report"]
    
    llm = get_llm()
    
    prompt = f"""
    基于调研报告，生成详细的文章大纲。
    
    【任务】{req}
    【调研报告】{report}
    
    请严格输出 JSON 格式（List[Dict]），字段包括：
    - "title": 章节标题
    - "desc": 本章详细写作指导（包含要点、逻辑流向）
    - "content": "" (留空)
    
    只输出 JSON，不要 Markdown 标记。
    """
    
    res = llm.invoke([HumanMessage(content=prompt)]).content
    clean_json = res.replace("```json", "").replace("```", "").strip()
    
    try:
        outline = json.loads(clean_json)
    except:
        outline = [{"title": "Error", "desc": "生成失败，请重试", "content": ""}]
        
    return {"current_outline": outline, "next": "END"}

# 5. [新增] 报告校准器 (ReportUpdater): 大纲修改后，反向补充调研报告
def report_updater_node(state: WriterState) -> dict:
    """当用户修改大纲后，AI 检查调研报告是否覆盖了新大纲的内容，并进行更新。"""
    old_report = state["research_report"]
    new_outline = state["current_outline"]
    
    llm = get_llm()
    
    outline_text = "\n".join([f"- {s['title']}: {s['desc']}" for s in new_outline])
    
    prompt = f"""
    用户修改了文章大纲，我们需要更新调研报告以匹配新结构。
    
    【旧调研报告】
    {old_report}
    
    【新大纲】
    {outline_text}
    
    请重新改写调研报告。保留旧报告中有价值的信息，但必须补充新大纲中涉及的新领域（如果旧报告没覆盖，请根据常识进行逻辑补充或标记需要后续查证）。
    保持 Markdown 格式。
    """
    
    new_report = llm.invoke([HumanMessage(content=prompt)]).content
    return {"research_report": new_report, "next": "END"}

# ==========================================
# PART 2: 迭代式正文写作 (Iterative Writing)
# ==========================================

def section_writer_node(state: WriterState) -> dict:
    outline = state["current_outline"]
    idx = state["current_section_index"]
    report = state["research_report"]
    generated_so_far = state.get("generated_content", "") # 之前所有章节的文本
    
    if idx < 0 or idx >= len(outline):
        return {"current_section_draft": "", "next": "END"}
    
    target_section = outline[idx]
    
    # 简单的上下文截断，防止 Token 溢出
    # 只取最近的 1000 个字符作为"上文衔接"，加上 Report 作为"全局指导"
    context_preview = generated_so_far[-1500:] if generated_so_far else "(这是第一章)"
    
    llm = get_llm()
    
    prompt = f"""
    你正在撰写一篇文章。请根据规划，撰写第 {idx+1} 章。
    
    【全局调研报告】
    {report}
    
    【文章已生成部分（前文）】
    ...{context_preview}
    
    【当前章节任务】
    标题：{target_section['title']}
    指导：{target_section['desc']}
    
    【写作要求】
    1. **承上启下**：注意与【前文】的逻辑衔接，不要突兀。
    2. **内容充实**：严格遵循本章指导。
    3. **格式**：Markdown，不要重复输出章节标题（除非为了强调），直接写正文。
    """
    
    draft = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {"current_section_draft": draft, "next": "END"}


# ==========================================
# 构建图
# ==========================================

# 1. 大纲生成流 (Plan -> Research -> Report -> Outline)
def build_outline_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Planner", write_planner_node)
    wf.add_node("Researcher", write_researcher_node)
    wf.add_node("ReportGenerator", report_generator_node)
    wf.add_node("OutlineGenerator", outline_generator_node)
    
    wf.set_entry_point("Planner")
    
    # 路由
    wf.add_conditional_edges(
        "Planner", 
        lambda x: x["next"], 
        {"Researcher": "Researcher", "ReportGenerator": "ReportGenerator"}
    )
    
    wf.add_edge("Researcher", "Planner")
    wf.add_edge("ReportGenerator", "OutlineGenerator")
    wf.add_edge("OutlineGenerator", END)
    
    return wf.compile()

# 2. 报告更新流 (用于修改大纲后)
def build_report_update_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Updater", report_updater_node)
    wf.set_entry_point("Updater")
    wf.add_edge("Updater", END)
    return wf.compile()

# 3. 写作流
def build_writing_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Writer", section_writer_node)
    wf.set_entry_point("Writer")
    wf.add_edge("Writer", END)
    return wf.compile()

outline_graph = build_outline_graph()
report_update_graph = build_report_update_graph()
writing_graph = build_writing_graph()