import json
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes import get_llm
# 移除旧的检索依赖，现在只靠 DeepSeek 大窗口阅读
# from src.storage import load_kbs 

# ==========================================
# 0. 缓存感知 System Prompt (核心设计)
# ==========================================
def get_cached_system_prompt(content: str) -> str:
    """
    构造符合 Context Caching 标准的 System Prompt。
    将全文放在开头，后续 Planner, Researcher, Writer 都复用此前缀。
    """
    return f"""你是一个专业的深度写作助手。
以下是项目的核心参考素材（已缓存全文），请基于此内容进行分析、规划和写作。
切勿编造素材中不存在的事实。

<DOCUMENT_START>
{content}
<DOCUMENT_END>
"""

# ==========================================
# PART 1: 调研与大纲生成 (全知视角)
# ==========================================

def plan_node(state: WriterState) -> dict:
    """规划师：阅读全文，制定调研方向"""
    req = state["user_requirement"]
    full_text = state["full_content"] # 获取缓存的全文
    outline = state.get("current_outline", [])
    loop = state.get("loop_count", 0)
    
    # 限制调研轮次
    if loop >= 3:
        return {"next": "ReportGenerator"}

    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    if outline:
        # 基于现有大纲反思
        task_prompt = f"""
        当前任务：完善调研。
        用户需求：{req}
        当前大纲：{json.dumps(outline, ensure_ascii=False)}
        
        请结合【全文内容】，分析大纲中哪些部分还缺乏深度或事实支撑？
        请提出 1 个具体的挖掘方向。
        """
    else:
        # 初始规划
        task_prompt = f"""
        当前任务：写作前期规划。
        用户需求：{req}
        
        请快速通读【全文内容】，为了写好这篇文章，我们需要重点梳理哪些信息？
        请提出 1 个具体的调研切入点。
        """
    
    plan = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
    return {
        "planning_steps": [plan],
        "next": "Researcher",
        "loop_count": loop + 1
    }

def research_node(state: WriterState) -> dict:
    """研究员：在全文中查找证据"""
    full_text = state["full_content"]
    plans = state.get("planning_steps", [])
    latest_plan = plans[-1] if plans else "通用分析"
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    task_prompt = f"""
    【调研目标】{latest_plan}
    
    请在【全文内容】中仔细查找相关事实、数据或案例。
    输出一段 300字左右的"调研笔记"，并在每一条发现后注明来源位置（如"根据文档前半部分..."）。
    """
    
    note = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
    return {
        "research_notes": [note],
        "next": "PlanCheck"
    }

def plan_check_node(state: WriterState) -> dict:
    loop = state.get("loop_count", 0)
    if loop >= 3:
        return {"next": "ReportGenerator"}
    return {"next": "Planner"}

def report_node(state: WriterState) -> dict:
    """报告生成：汇总笔记 + 全文理解"""
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
    
    请结合【全文内容】和笔记，撰写《深度调研报告》。
    包含：核心观点、关键数据、逻辑脉络。
    """
    
    report = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    return {"research_report": report, "next": "Outliner"}

def outline_node(state: WriterState) -> dict:
    """大纲生成"""
    req = state["user_requirement"]
    report = state["research_report"]
    full_text = state["full_content"]
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    task_prompt = f"""
    基于调研报告，设计文章大纲。
    【用户需求】{req}
    【调研报告】{report}
    
    请输出 JSON 格式（List[Dict]），包含 title, desc。
    示例：["title": "...", "desc": "..."]
    """
    
    res = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
    # JSON 清洗
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
# PART 2: 迭代写作 (复用缓存)
# ==========================================

def iterative_writer_node(state: WriterState) -> dict:
    full_text = state["full_content"] # <--- 再次复用缓存
    report = state["research_report"]
    outline = state["current_outline"]
    idx = state["current_section_index"]
    previous_context = state.get("full_draft", "")
    
    if idx < 0 or idx >= len(outline):
        return {"current_section_content": "", "next": "END"}
    
    target_section = outline[idx]
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    prompt = f"""
    正在撰写第 {idx + 1} 部分：【{target_section['title']}】。
    
    【调研报告】{report}
    【本章指引】{target_section['desc']}
    【已写内容】{previous_context[-3000:]}
    
    【要求】
    1. 充分利用【全文内容】中的细节。
    2. 紧密承接上文。
    3. 不重复已写内容。
    4. 直接输出 Markdown 正文。
    """
    
    content = llm.invoke([system_msg, HumanMessage(content=prompt)]).content
    return {"current_section_content": content, "next": "END"}

# ==========================================
# PART 3: 大纲重构 (复用缓存)
# ==========================================

def outline_refiner_node(state: WriterState) -> dict:
    full_text = state["full_content"]
    current_outline = state["current_outline"]
    current_report = state["research_report"]
    instruction = state["edit_instruction"]
    req = state["user_requirement"]
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_cached_system_prompt(full_text))
    
    # 1. 更新报告
    report_prompt = f"""
    用户指令：{instruction}
    
    请基于【全文内容】，补充更新《调研报告》以支持该指令。
    【原报告】{current_report}
    """
    new_report = llm.invoke([system_msg, HumanMessage(content=report_prompt)]).content
    
    # 2. 重构大纲
    outline_prompt = f"""
    基于新报告和指令重构大纲。
    【新报告】{new_report}
    【旧大纲】{json.dumps(current_outline, ensure_ascii=False)}
    
    输出纯 JSON。
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

# 辅助节点：社交摘要 (不需要缓存全文，只看生成结果)
def social_summary_node(state: WriterState) -> dict:
    from src.write_flow import generate_viral_card_content
    # 这里我们简单mock一下，或者你需要把 generate_viral_card_content 定义在这里
    # 为了防止循环引用，我们直接在这里实现简版
    report = state["research_report"]
    outline = state["current_outline"]
    
    full_gen = ""
    for sec in outline:
        if sec.get('content'):
            full_gen += sec['content']
            
    # 简单调用 LLM
    llm = get_llm()
    prompt = f"写一个社交媒体摘要。\n标题：{report[:30]}\n内容：{full_gen[:2000]}"
    summary = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {"social_summary": summary, "next": "END"}

# 构建图
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

def build_refine_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Refiner", outline_refiner_node)
    wf.set_entry_point("Refiner")
    wf.add_edge("Refiner", END)
    return wf.compile()

research_graph = build_research_graph()
drafting_graph = build_drafting_graph()
refine_graph = build_refine_graph()

# 导出 generate_viral_card_content 供前端使用 (保持兼容性)
def generate_viral_card_content(title, full_text):
    llm = get_llm()
    prompt = f"写社交摘要。\n标题：{title}\n内容：{full_text[:3000]}"
    return llm.invoke([HumanMessage(content=prompt)]).content