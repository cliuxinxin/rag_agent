import json
import time # 引入 time
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.state import DeepWriteState
from src.prompts_v3 import (
    get_topic_gen_prompt, # 新增引用
    get_analyst_prompt,
    get_architect_prompt,
    get_writer_prompt,
    get_reviewer_prompt,
    get_polisher_prompt
)
from src.logger import get_logger # 引入日志

logger = get_logger("WriteNodeV3")

# [新增] 0. 主题生成节点
def topic_generator_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    # 如果用户没填内容，给个默认值防止报错
    content = state.get("raw_content") or "无内容"
    
    prompt = get_topic_gen_prompt(content)
    topic = llm.invoke([HumanMessage(content=prompt)]).content.strip().replace('"', '')
    
    return {
        "topic": topic,
        "run_logs": [f"💡 已自动生成主题：{topic}"]
    }

# 1. 分析师
def analyst_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    prompt = get_analyst_prompt(state["raw_content"], state["topic"])
    response = llm.invoke([HumanMessage(content=prompt)]).content
    return {
        "topic_analysis": response,
        "run_logs": ["✅ [分析师] 已完成素材提炼与立意分析"]
    }

# 2. 架构师
def architect_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    prompt = get_architect_prompt(state["topic"], state["topic_analysis"], state["user_instruction"])
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        outline = json.loads(clean_json)
    except:
        # 降级策略
        outline = [
            {"title": "引言", "gist": "介绍背景"},
            {"title": "正文", "gist": "核心内容阐述"},
            {"title": "结论", "gist": "总结观点"}
        ]
        
    return {
        "outline": outline,
        "current_section_index": 0,
        "section_drafts": [], # 初始化清空
        "run_logs": [f"✅ [架构师] 已设计 {len(outline)} 个章节的大纲"]
    }

# 3. 接力撰稿人 (核心修复)
def writer_node(state: DeepWriteState) -> dict:
    idx = state["current_section_index"]
    outline = state["outline"]
    drafts = state["section_drafts"]
    
    # 安全检查
    if idx >= len(outline):
        return {}

    current_sec = outline[idx]
    
    # 构造前文上下文
    prev_context = "\n\n".join(drafts) if drafts else "(这是文章的开头)"
    outline_str = json.dumps(outline, ensure_ascii=False, indent=1)
    
    llm = get_llm()
    prompt = get_writer_prompt(current_sec["title"], current_sec["gist"], prev_context, outline_str)
    
    # === [修复 1] 记录开始日志 ===
    start_log = f"⏳ [撰稿人] 正在撰写第 {idx+1}/{len(outline)} 章：{current_sec['title']}..."
    logger.info(start_log)
    
    # === [修复 2] 增加异常捕获，防止卡死 ===
    try:
        # 调用 LLM
        content = llm.invoke([HumanMessage(content=prompt)]).content
        
        # 加上 Markdown 标题
        formatted_section = f"## {current_sec['title']}\n\n{content}"
        
        success_log = f"✅ [撰稿人] 完成第 {idx+1} 章"
        
        return {
            "section_drafts": [formatted_section],
            "current_section_index": idx + 1,
            "run_logs": [start_log, success_log] # 把开始和结束都发给前端
        }
        
    except Exception as e:
        logger.error(f"章节 {idx+1} 生成失败: {e}", exc_info=True)
        # 生成失败时的降级处理：生成一个错误提示，保证流程不中断
        error_content = f"## {current_sec['title']}\n\n*(本章生成时发生网络错误，请稍后手动润色)*\n\n> Error: {str(e)}"
        
        return {
            "section_drafts": [error_content],
            "current_section_index": idx + 1,
            "run_logs": [start_log, f"❌ [撰稿人] 第 {idx+1} 章生成出错，已跳过"]
        }

# 4. 主编
def reviewer_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    
    llm = get_llm()
    prompt = get_reviewer_prompt(full_draft, state["user_instruction"])
    critique = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {
        "critique_notes": critique,
        "run_logs": ["🧐 [主编] 全文审阅完成，提出修改意见"]
    }

# 5. 润色师
def polisher_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    
    llm = get_llm()
    prompt = get_polisher_prompt(full_draft, state["critique_notes"])
    final_article = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {
        "final_article": final_article,
        "run_logs": ["✨ [润色师] 最终定稿完成！"]
    }