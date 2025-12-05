import json
from langchain_core.messages import HumanMessage, SystemMessage
from src.nodes.common import get_llm
from src.prompts import (
    get_newsroom_base_prompt,
    get_angle_generator_prompt,
    get_outline_architect_prompt,
    get_internal_researcher_prompt,
    get_section_drafter_prompt,
    get_editor_reviewer_prompt,
    get_final_polisher_prompt
)
from src.state import NewsroomState


# === 1. 策划阶段 (Planning) ===
def angle_generator_node(state: NewsroomState) -> dict:
    """首席策划：生成切入角度"""
    full_text = state["full_content"]
    req = state["user_requirement"]

    llm = get_llm()
    # Base Prompt 命中缓存
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    user_msg = HumanMessage(content=get_angle_generator_prompt())

    response = llm.invoke([base_sys, user_msg]).content

    # JSON 解析
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        angles = json.loads(clean_json)
    except Exception:
        angles = [
            {"title": "深度分析", "desc": "基于文档内容的标准分析", "reasoning": "Fallback"},
            {"title": "要点提炼", "desc": "快速提取核心信息", "reasoning": "Fallback"},
            {"title": "批判性视角", "desc": "寻找文档中的逻辑漏洞", "reasoning": "Fallback"}
        ]

    return {"generated_angles": angles}


def outline_architect_node(state: NewsroomState) -> dict:
    """架构师：生成大纲"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    angle_data = state.get("selected_angle", {})
    angle_str = f"{angle_data.get('title')} - {angle_data.get('desc')}"

    llm = get_llm()
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    user_msg = HumanMessage(content=get_outline_architect_prompt(angle_str))

    response = llm.invoke([base_sys, user_msg]).content

    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        outline = json.loads(clean_json)
    except Exception:
        outline = [{"title": "生成失败", "gist": "请重试", "key_facts": ""}]

    return {"outline": outline, "current_section_index": 0, "section_drafts": [], "full_draft": ""}


# === 2. 采编与撰写循环 (Drafting Loop) ===
def internal_researcher_node(state: NewsroomState) -> dict:
    """内部探员：在文档中查证事实"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    outline = state["outline"]
    idx = state["current_section_index"]

    if idx >= len(outline):
        return {"next": "Reviewer"}

    section = outline[idx]

    llm = get_llm()
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    user_msg = HumanMessage(content=get_internal_researcher_prompt(section['title'], section.get('key_facts', '')))

    notes = llm.invoke([base_sys, user_msg]).content
    return {"research_cache": notes, "next": "Drafter"}


def section_drafter_node(state: NewsroomState) -> dict:
    """撰稿人：基于笔记写一章"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    outline = state["outline"]
    idx = state["current_section_index"]
    notes = state.get("research_cache", "")

    drafts = state.get("section_drafts", [])
    prev_context = drafts[-1] if drafts else "（这是文章的开头）"

    section = outline[idx]

    llm = get_llm()
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    user_msg = HumanMessage(content=get_section_drafter_prompt(section['title'], notes, prev_context))

    content = llm.invoke([base_sys, user_msg]).content

    # 清洗：去掉可能重复生成的标题
    clean_content = content.replace(f"# {section['title']}", "").replace(f"## {section['title']}", "").strip()

    new_drafts = drafts + [f"## {section['title']}\n\n{clean_content}"]

    return {
        "section_drafts": new_drafts,
        "current_section_index": idx + 1,
        "next": "Dispatcher"
    }


def dispatcher_node(state: NewsroomState) -> dict:
    """调度器：决定是继续写还是去审阅"""
    idx = state["current_section_index"]
    outline = state["outline"]
    if idx < len(outline):
        return {"next": "Researcher"}
    full_text = "\n\n".join(state["section_drafts"])
    return {"next": "Reviewer", "full_draft": full_text}


# === 3. 审阅与润色 (Review & Polish) ===
def reviewer_node(state: NewsroomState) -> dict:
    """主编：审阅"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    full_draft = state["full_draft"]

    llm = get_llm()
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    user_msg = HumanMessage(content=get_editor_reviewer_prompt(full_draft))

    critique = llm.invoke([base_sys, user_msg]).content
    return {"critique_notes": critique, "next": "Polisher"}


def polisher_node(state: NewsroomState) -> dict:
    """润色师：定稿"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    full_draft = state["full_draft"]
    critique = state["critique_notes"]

    llm = get_llm()
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    user_msg = HumanMessage(content=get_final_polisher_prompt(full_draft, critique))

    final_article = llm.invoke([base_sys, user_msg]).content
    return {"final_article": final_article, "next": "END"}

