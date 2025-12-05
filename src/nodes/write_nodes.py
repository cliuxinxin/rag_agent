# src/nodes/write_nodes.py
import json
from langchain_core.messages import HumanMessage, SystemMessage
from src.nodes.common import get_llm
from src.prompts import get_context_caching_system_prompt, get_writer_iteration_prompt
from src.state import WriterState

# === 1. 规划与调研节点 ===

def plan_node(state: WriterState) -> dict:
    """规划师：阅读全文，制定调研方向"""
    req = state["user_requirement"]
    full_text = state["full_content"]
    outline = state.get("current_outline", [])
    loop = state.get("loop_count", 0)
    
    if loop >= 3:
        return {"next": "ReportGenerator"}

    llm = get_llm()
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    
    if outline:
        task_prompt = f"""
        当前任务：完善调研。用户需求：{req}
        当前大纲：{json.dumps(outline, ensure_ascii=False)}
        请结合【全文内容】，提出 1 个具体的挖掘方向。
        """
    else:
        task_prompt = f"""
        当前任务：写作前期规划。用户需求：{req}
        请快速通读【全文内容】，提出 1 个具体的调研切入点。
        """
    
    plan = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    return {"planning_steps": [plan], "next": "Researcher", "loop_count": loop + 1}

def research_node(state: WriterState) -> dict:
    full_text = state["full_content"]
    plans = state.get("planning_steps", [])
    latest_plan = plans[-1] if plans else "通用分析"
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    
    task_prompt = f"""
    【调研目标】{latest_plan}
    请在【全文内容】中仔细查找相关事实、数据或案例。
    输出一段 300字左右的"调研笔记"。
    """
    note = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    return {"research_notes": [note], "next": "PlanCheck"}

def plan_check_node(state: WriterState) -> dict:
    loop = state.get("loop_count", 0)
    if loop >= 3:
        return {"next": "ReportGenerator"}
    return {"next": "Planner"}

def report_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    full_text = state["full_content"]
    notes = state.get("research_notes", [])
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    notes_text = "\n\n".join(notes)
    
    task_prompt = f"""
    你是一个高级分析师。需求：{req}
    笔记：{notes_text}
    请结合【全文内容】和笔记，撰写《深度调研报告》。
    """
    report = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    return {"research_report": report, "next": "Outliner"}

def outline_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    report = state["research_report"]
    full_text = state["full_content"]
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    
    task_prompt = f"""
    基于调研报告，设计文章大纲。需求：{req}
    报告：{report}
    请输出 JSON 格式（List[Dict]），包含 title, desc。
    """
    res = llm.invoke([system_msg, HumanMessage(content=task_prompt)]).content
    
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

# === 2. 迭代写作节点 ===

def iterative_writer_node(state: WriterState) -> dict:
    full_text = state["full_content"]
    report = state["research_report"]
    outline = state["current_outline"]
    idx = state["current_section_index"]
    previous_context = state.get("full_draft", "")
    
    if idx < 0 or idx >= len(outline):
        return {"current_section_content": "", "next": "END"}
    
    target_section = outline[idx]
    llm = get_llm()
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    
    prompt = get_writer_iteration_prompt(idx, target_section['title'], report, target_section['desc'], previous_context)
    content = llm.invoke([system_msg, HumanMessage(content=prompt)]).content
    
    # 清洗
    clean_content = content.strip()
    if clean_content.startswith(target_section['title']):
        clean_content = clean_content[len(target_section['title']):].strip()
    import re
    clean_content = re.sub(r'^#+\s*' + re.escape(target_section['title']) + r'\s*\n', '', clean_content, flags=re.IGNORECASE).strip()

    return {"current_section_content": clean_content, "next": "END"}

def social_summary_node(state: WriterState) -> dict:
    # 简单的社交媒体摘要生成，不依赖 state 的 next
    llm = get_llm()
    report = state["research_report"]
    outline = state["current_outline"]
    full_gen = "".join([sec.get('content', '') for sec in outline])
    
    prompt = f"写一个社交媒体摘要。\n标题：{report[:30]}\n内容：{full_gen[:2000]}"
    summary = llm.invoke([HumanMessage(content=prompt)]).content
    return {"social_summary": summary, "next": "END"}

# === 3. 大纲重构节点 ===

def outline_refiner_node(state: WriterState) -> dict:
    full_text = state["full_content"]
    current_outline = state["current_outline"]
    current_report = state["research_report"]
    instruction = state["edit_instruction"]
    
    llm = get_llm()
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    
    # 1. 更新报告
    report_prompt = f"用户指令：{instruction}\n基于全文更新《调研报告》：\n{current_report}"
    new_report = llm.invoke([system_msg, HumanMessage(content=report_prompt)]).content
    
    # 2. 重构大纲
    outline_prompt = f"基于新报告和指令重构大纲。\n新报告：{new_report}\n旧大纲：{json.dumps(current_outline, ensure_ascii=False)}\n输出纯 JSON。"
    res = llm.invoke([system_msg, HumanMessage(content=outline_prompt)]).content
    
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

# === 辅助工具函数 ===
def generate_viral_card_content(title, full_text):
    """前端调用的辅助函数"""
    llm = get_llm()
    prompt = f"写社交摘要。\n标题：{title}\n内容：{full_text[:3000]}"
    return llm.invoke([HumanMessage(content=prompt)]).content