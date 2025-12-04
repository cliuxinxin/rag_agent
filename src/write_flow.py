import json
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes import get_llm
# 移除旧的检索依赖
# from src.storage import load_kbs
# from langchain_community.retrievers import BM25Retriever

# ==========================================
# 0. 缓存感知 System Prompt
# ==========================================
def get_cached_system_prompt(content: str) -> str:
    """
    构造符合 DeepSeek Context Caching 标准的 System Prompt。
    将全文放在开头，后续所有对话都能击中缓存。
    """
    return f"""你是一个专业的深度写作助手。
以下是项目的核心参考素材（已缓存全文），请基于此内容进行分析、规划和写作。
切勿编造素材中不存在的事实。

<DOCUMENT_START>
{content}
<DOCUMENT_END>
"""

# ==========================================
# PART 1: 基于全文的 调研与大纲生成
# ==========================================

def plan_node(state: WriterState) -> dict:
    """
    规划师：阅读全文，决定需要从文中挖掘哪些具体信息。
    """
    req = state["user_requirement"]
    full_text = state["full_content"]
    outline = state.get("current_outline", [])
    loop = state.get("loop_count", 0)
    
    if loop >= 3:
        return {"next": "ReportGenerator"}

    llm = get_llm()
    
    # 构建 Prompt：利用缓存的 System Prompt
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    if outline:
        # 如果是基于已有大纲的反思
        task_prompt = f"""
        当前任务：完善写作调研。
        用户需求：{req}
        当前大纲：{json.dumps(outline, ensure_ascii=False)}
        
        请结合【全文内容】，分析大纲中哪些章节的内容在目前的调研中还不够扎实？
        请提出 1 个最需要深入挖掘的问题或方向（例如："挖掘文中关于xxx的具体数据"）。
        """
    else:
        # 初始规划
        task_prompt = f"""
        当前任务：为写作项目做前期规划。
        用户需求：{req}
        
        请快速通读【全文内容】，为了写好这篇文章，我们需要重点梳理哪些方面的信息？
        请提出 1 个具体的调研切入点。
        """
    
    plan = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
    return {
        "planning_steps": [plan],
        "next": "Researcher",
        "loop_count": loop + 1
    }

def research_node(state: WriterState) -> dict:
    """
    研究员：带着问题去读全文，提取素材。
    (不再用搜索，而是用 LLM 阅读理解)
    """
    full_text = state["full_content"]
    plans = state.get("planning_steps", [])
    latest_plan = plans[-1] if plans else "通用分析"
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    task_prompt = f"""
    【调研目标】{latest_plan}
    
    请在【全文内容】中仔细查找与该目标相关的所有事实、数据、观点或案例。
    
    要求：
    1. 摘录原文的关键信息。
    2. 如果原文有隐含逻辑，请进行总结。
    3. 输出一段 300字左右的"调研笔记"。
    """
    
    note = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
    return {
        "research_notes": [note], # 追加笔记
        "next": "PlanCheck"
    }

def plan_check_node(state: WriterState) -> dict:
    loop = state.get("loop_count", 0)
    # 稍微增加一轮，因为现在阅读速度快
    if loop >= 3:
        return {"next": "ReportGenerator"}
    return {"next": "Planner"}

def report_node(state: WriterState) -> dict:
    """
    报告生成器：汇总笔记 + 全文宏观理解
    """
    req = state["user_requirement"]
    full_text = state["full_content"]
    notes = state.get("research_notes", [])
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    notes_text = "\n\n".join(notes)
    
    task_prompt = f"""
    你是一个高级分析师。
    
    【写作需求】{req}
    【专项调研笔记】
    {notes_text}
    
    请结合【全文内容】和【调研笔记】，撰写一份逻辑严密的《深度调研报告》。
    这份报告将作为后续正文写作的唯一事实依据。
    
    包含：
    1. 核心主旨与背景。
    2. 关键论据与数据支撑。
    3. 建议的文章结构脉络。
    """
    
    report = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    return {"research_report": report, "next": "Outliner"}

def outline_node(state: WriterState) -> dict:
    """大纲生成器"""
    req = state["user_requirement"]
    report = state["research_report"]
    full_text = state["full_content"] # 依然传入全文，保持 Context 击中
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    task_prompt = f"""
    基于调研报告，设计文章大纲。
    
    【用户需求】{req}
    【调研报告】{report}
    
    请输出严格的 JSON 格式（List[Dict]），包含 title, desc。
    示例：["title": "...", "desc": "..."]
    """
    
    res = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
    # --- JSON 清洗逻辑 (保持不变) ---
    clean_json = res.replace("```json", "").replace("```", "").strip()
    start_idx = clean_json.find("[")
    end_idx = clean_json.rfind("]")
    new_outline = []
    if start_idx != -1 and end_idx != -1:
        try:
            new_outline = json.loads(clean_json[start_idx : end_idx + 1])
        except:
            new_outline = [{"title": "格式解析失败", "desc": "请重试"}]
    else:
         new_outline = [{"title": "生成失败", "desc": res[:100]}]

    return {"current_outline": new_outline, "next": "END"}

# ==========================================
# PART 2: 迭代写作 Agent
# ==========================================

# 辅助函数：生成病毒摘要 (保持不变，也可以加上 Cache)
def generate_viral_card_content(title, full_text):
    """专门生成用于长图头部的病毒式摘要"""
    llm = get_llm()
    prompt = f"""
    请为这篇文章写一段"社交媒体摘要"。
    标题：{title}
    内容：{full_text[:4000]}...
    
    格式：
    💡 核心洞察：...
    🔥 关键数据：...
    🚀 启示：...
    """
    return llm.invoke([HumanMessage(content=prompt)]).content

# ==========================================
# PART 2: 迭代写作 Agent (Context Caching 核心)
# ==========================================

def iterative_writer_node(state: WriterState) -> dict:
    full_text = state["full_content"] # <--- 核心：原文缓存
    report = state["research_report"]
    outline = state["current_outline"]
    idx = state["current_section_index"]
    previous_context = state.get("full_draft", "") # 已生成的正文
    
    if idx < 0 or idx >= len(outline):
        return {"current_section_content": "", "next": "END"}
    
    target_section = outline[idx]
    llm = get_llm()
    
    # 构造能够击中缓存的 Prompt
    # 顺序：System(原文) -> Human(任务 + 报告 + 上文)
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    prompt = f"""
    你正在撰写文章的第 {idx + 1} 部分：【{target_section['title']}】。
    
    【调研报告 (Fact Base)】
    {report}
    
    【本章指引】
    {target_section['desc']}
    
    【已写内容 (Context)】
    {previous_context[-4000:]} 
    
    【写作要求】
    1. **利用原文**：请随时回溯 System Prompt 中的【全文内容】，引用具体的细节、金句或数据，使文章具有颗粒度。
    2. **连贯性**：紧密承接【已写内容】的结尾，不要生硬跳转。
    3. **去重**：不要重复【已写内容】中已经详细论述过的观点。
    4. **格式**：直接输出 Markdown 正文，不带标题。
    """
    
    content = llm.invoke([system_msg, HumanMessage(content=prompt)]).content
    return {"current_section_content": content, "next": "END"}

def social_summary_node(state: WriterState) -> dict:
    """生成社交媒体摘要节点"""
    # 这里的逻辑主要是处理生成后的文章，不需要读取原始 cached full_content
    # 如果需要引用原始数据，可以加，但通常基于生成的文章写摘要就够了
    report = state["research_report"]
    outline = state["current_outline"]
    
    full_generated_text = ""
    for section in outline:
        if section.get('content'):
            full_generated_text += f"## {section['title']}\n\n{section['content']}\n\n"
            
    title = report[:50]
    summary = generate_viral_card_content(title, full_generated_text)
    
    return {"social_summary": summary, "next": "END"}

# ==========================================
# 构建图
# ==========================================

# 构建图 (结构基本不变，只是 Node 内部逻辑变了)
def build_research_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Planner", plan_node)
    wf.add_node("Researcher", research_node)
    wf.add_node("PlanCheck", plan_check_node)
    wf.add_node("ReportGenerator", report_node)
    wf.add_node("Outliner", outline_node)
    
    wf.set_entry_point("Planner")
    wf.add_edge("Planner", "Researcher")
    wf.add_edge("Researcher", "PlanCheck")
    wf.add_conditional_edges("PlanCheck", lambda x: x["next"], {"Planner": "Planner", "ReportGenerator": "ReportGenerator"})
    wf.add_edge("ReportGenerator", "Outliner")
    wf.add_edge("Outliner", END)
    return wf.compile()

def build_drafting_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Writer", iterative_writer_node)
    wf.add_node("SocialSummary", social_summary_node)
    wf.set_entry_point("Writer")
    wf.add_edge("Writer", "SocialSummary")
    wf.add_edge("SocialSummary", END)
    return wf.compile()

# ==========================================
# PART 3: 大纲重构 (Refiner)
# ==========================================

def outline_refiner_node(state: WriterState) -> dict:
    full_text = state["full_content"] # <--- 核心
    current_outline = state["current_outline"]
    current_report = state["research_report"]
    instruction = state["edit_instruction"]
    req = state["user_requirement"]
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    # 1. 更新报告
    report_prompt = f"""
    用户希望修改文章结构。请先基于【全文内容】补充调研报告。
    
    【原需求】{req}
    【原报告】{current_report}
    【修改指令】{instruction}
    
    请输出更新后的调研报告全文。
    """
    new_report = llm.invoke([system_msg, HumanMessage(content=report_prompt)]).content
    
    # 2. 重构大纲
    outline_prompt = f"""
    基于新报告和指令，重构大纲。
    
    【新报告】{new_report}
    【旧大纲】{json.dumps(current_outline, ensure_ascii=False)}
    【修改指令】{instruction}
    
    请输出纯 JSON 大纲 (List[Dict])。
    """
    res = llm.invoke([system_msg, HumanMessage(content=outline_prompt)]).content
    
    # JSON 清洗
    clean_json = res.replace("```json", "").replace("```", "").strip()
    start = clean_json.find("[")
    end = clean_json.rfind("]")
    new_outline = current_outline
    if start != -1 and end != -1:
        try:
            new_outline = json.loads(clean_json[start:end+1])
        except: pass
            
    return {
        "research_report": new_report,
        "current_outline": new_outline,
        "next": "END"
    }

def build_refine_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Refiner", outline_refiner_node)
    wf.set_entry_point("Refiner")
    wf.add_edge("Refiner", END)
    return wf.compile()

research_graph = build_research_graph()
drafting_graph = build_drafting_graph()
refine_graph = build_refine_graph()
