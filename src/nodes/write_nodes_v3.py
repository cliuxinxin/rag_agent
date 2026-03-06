import json
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.state import DeepWriteState
from src.logger import get_logger
from src.prompts_v3 import (
    get_topic_gen_prompt,
    get_analyst_prompt,
    get_architect_prompt,
    get_writer_prompt,
    get_reviewer_prompt,
    get_polisher_prompt
)

logger = get_logger("DeepWrite_V3")

# 0. 主题生成节点
def topic_generator_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    content = state.get("raw_content") or "无内容"
    
    logger.info("开始生成主题...")
    
    prompt = get_topic_gen_prompt(content)
    topic = llm.invoke([HumanMessage(content=prompt)]).content.strip().replace('"', '')
    
    msg = f"💡 已自动生成主题：{topic}"
    logger.info(msg)
    
    return {
        "topic": topic,
        "run_logs": [msg]
    }

# 1. 分析师
def analyst_node(state: DeepWriteState) -> dict:
    logger.info("分析师正在提炼素材...")
    
    llm = get_llm()
    prompt = get_analyst_prompt(state["raw_content"], state["topic"])
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    msg = "✅ [分析师] 已完成素材提炼与立意分析"
    logger.info(msg)
    
    return {
        "topic_analysis": response,
        "run_logs": [msg]
    }

# 2. 架构师
def architect_node(state: DeepWriteState) -> dict:
    logger.info("架构师正在设计大纲...")
    
    llm = get_llm()
    prompt = get_architect_prompt(state["topic"], state["topic_analysis"], state["user_instruction"])
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        outline = json.loads(clean_json)
    except Exception as e:
        logger.error(f"大纲解析失败: {e}")
        outline = [
            {"title": "引言", "gist": "介绍背景"},
            {"title": "正文", "gist": "核心内容阐述"},
            {"title": "结论", "gist": "总结观点"}
        ]
        
    msg = f"✅ [架构师] 已设计 {len(outline)} 个章节的大纲"
    logger.info(msg)
        
    return {
        "outline": outline,
        "current_section_index": 0,
        "section_drafts": [],
        "run_logs": [msg]
    }

# 3. 接力撰稿人
def writer_node(state: DeepWriteState) -> dict:
    idx = state["current_section_index"]
    outline = state["outline"]
    drafts = state["section_drafts"]
    
    if idx >= len(outline):
        return {}

    current_sec = outline[idx]
    
    start_msg = f"⏳ [撰稿人] 正在撰写第 {idx+1}/{len(outline)} 章：{current_sec['title']}..."
    logger.info(start_msg)
    
    prev_context = "\n\n".join(drafts) if drafts else "(这是文章的开头)"
    outline_str = json.dumps(outline, ensure_ascii=False, indent=1)
    
    llm = get_llm()
    prompt = get_writer_prompt(current_sec["title"], current_sec["gist"], prev_context, outline_str)
    
    try:
        content = llm.invoke([HumanMessage(content=prompt)]).content
        formatted_section = f"## {current_sec['title']}\n\n{content}"
        
        end_msg = f"✅ [撰稿人] 完成第 {idx+1} 章"
        logger.info(end_msg)
        
        return {
            "section_drafts": [formatted_section],
            "current_section_index": idx + 1,
            "run_logs": [start_msg, end_msg]
        }
    except Exception as e:
        err_msg = f"❌ [撰稿人] 第 {idx+1} 章生成出错: {str(e)}"
        logger.error(err_msg)
        
        error_content = f"## {current_sec['title']}\n\n*(生成失败)*"
        return {
            "section_drafts": [error_content],
            "current_section_index": idx + 1,
            "run_logs": [start_msg, err_msg]
        }

# 4. 主编
def reviewer_node(state: DeepWriteState) -> dict:
    logger.info("主编正在审阅全文...")
    full_draft = "\n\n".join(state["section_drafts"])
    
    llm = get_llm()
    prompt = get_reviewer_prompt(full_draft, state["user_instruction"])
    critique = llm.invoke([HumanMessage(content=prompt)]).content
    
    msg = "🧐 [主编] 全文审阅完成，提出修改意见"
    logger.info(msg)
    
    return {
        "critique_notes": critique,
        "run_logs": [msg]
    }

# 5. 润色师
def polisher_node(state: DeepWriteState) -> dict:
    logger.info("润色师正在进行最终定稿...")
    full_draft = "\n\n".join(state["section_drafts"])
    
    llm = get_llm()
    prompt = get_polisher_prompt(full_draft, state["critique_notes"])
    final_article = llm.invoke([HumanMessage(content=prompt)]).content
    
    msg = "✨ [润色师] 最终定稿完成！"
    logger.info(msg)
    
    return {
        "final_article": final_article,
        "run_logs": [msg]
    }