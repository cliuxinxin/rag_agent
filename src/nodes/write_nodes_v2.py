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
# [新增]
from src.tools.search import tavily_search


# === 1. 策划阶段 (Planning) ===
# [新增] 宏观搜索节点 (专门负责搜)
def macro_search_node(state: NewsroomState) -> dict:
    """策划阶段：宏观背景搜索"""
    req = state["user_requirement"]
    enable_search = state.get("enable_web_search", False)
    llm = get_llm()
    
    if not enable_search:
        return {"macro_search_context": "", "run_logs": ["⏭️ 未开启联网，跳过背景搜索..."]}
    
    # 1. 生成搜索词
    query_gen_prompt = f"基于用户需求: '{req}'，生成一个用于Google搜索背景信息的关键词。只输出词，不要解释。"
    keyword = llm.invoke([HumanMessage(content=query_gen_prompt)]).content.strip().replace('"', '')
    
    # 2. 执行搜索
    log_msg = f"🌍 [策划] 正在全网搜索大背景: '{keyword}'..."
    raw_res = tavily_search(keyword, max_results=3)
    
    # 3. 返回结果和日志
    context = raw_res if raw_res else ""
    return {
        "macro_search_context": context, 
        "run_logs": [log_msg, f"✅ 已找到相关背景资料 ({len(context)} chars)"]
    }


def angle_generator_node(state: NewsroomState) -> dict:
    """首席策划：生成切入角度 (只负责生成)"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    # [修改] 直接从 State 获取搜索结果，不再自己搜
    search_context = state.get("macro_search_context", "")

    llm = get_llm()
    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    
    # 传入 prompt
    user_msg = HumanMessage(content=get_angle_generator_prompt(search_context))
    response = llm.invoke([base_sys, user_msg]).content

    # ... (JSON 解析代码不变) ...
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
    """内部探员：在文档中查证事实 (支持微观搜索)"""
    full_text = state["full_content"]
    req = state["user_requirement"]
    outline = state["outline"]
    idx = state["current_section_index"]
    enable_search = state.get("enable_web_search", False) # 获取开关

    if idx >= len(outline):
        return {"next": "Reviewer"}

    section = outline[idx]
    llm = get_llm()
    
    # [新增] 微观搜索
    search_context = ""
    logs = [] # [新增] 日志列表
    
    if enable_search:
        query = f"{section['title']} {section.get('key_facts', '')}"
        # [新增] 记录日志
        logs.append(f"🌍 [采编] 正在核实第 {idx+1} 章数据: '{query}'")
        
        # 搜索 (只取前2条，保证速度)
        raw_res = tavily_search(query, max_results=2)
        if raw_res:
            search_context = raw_res
            logs.append("✅ 网络取证完成")
        else:
            logs.append("⚠️ 网络搜索无结果，使用本地文档")

    base_sys = SystemMessage(content=get_newsroom_base_prompt(full_text, req))
    # [修改] 传入 search_context
    user_msg = HumanMessage(content=get_internal_researcher_prompt(
        section['title'], 
        section.get('key_facts', ''),
        search_context # <--- 传入
    ))

    notes = llm.invoke([base_sys, user_msg]).content
    # [修改] 返回 logs
    return {"research_cache": notes, "next": "Drafter", "run_logs": logs}


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