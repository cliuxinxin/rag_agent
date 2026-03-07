import json
import time
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.state import DeepWriteState
from src.logger import get_logger, log_llm_trace
from src.db import update_project_draft, update_project_outline, update_project_title
from src.prompts_v3 import (
    get_topic_gen_prompt,
    get_analyst_prompt,
    get_architect_prompt,
    get_writer_prompt,
    get_reviewer_prompt,
    get_polisher_prompt
)

logger = get_logger("DeepWrite_V3")

# === 辅助函数：带详细日志的 LLM 调用 (异步版本) ===
async def invoke_with_logging(llm, messages, stage_name: str, project_id: str = "N/A") -> str:
    """
    封装 LLM 异步调用，记录详细的输入输出日志和耗时，支持 project_id 链路追踪
    """
    start_time = time.time()
    
    # 构造 Prompt 文本用于记录
    prompt_content = "\n".join([m.content for m in messages])
    
    logger.info(f"[{project_id}] 🚀 [{stage_name}] 请求 LLM (Input: {len(prompt_content)} chars)")
    
    try:
        # 2. 执行异步调用
        response = await llm.ainvoke(messages)
        content = response.content
        duration = time.time() - start_time
        
        # 1. 记录简要日志到 app.log
        logger.info(f"[{project_id}] ✅ [{stage_name}] 完成 | {duration:.2f}s | Output: {len(content)} chars")
        
        # 2. 记录详细日志到 llm_trace.log (方便你 Debug 优化 Prompt)
        log_llm_trace(f"{project_id}::{stage_name}", prompt_content, content, duration)
        
        return content
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{project_id}] ❌ [{stage_name}] 失败 | {duration:.2f}s | Err: {e}")
        raise e

# === 节点定义 ===

# 0. 主题生成
async def topic_generator_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    content = state.get("raw_content") or "无内容"
    project_id = state.get("project_id", "UNKNOWN")
    
    logger.info(f"[{project_id}] 🎬 [TopicGen] 开始工作...")
    prompt = get_topic_gen_prompt(content)
    
    topic = (await invoke_with_logging(llm, [HumanMessage(content=prompt)], "TopicGen", project_id)).strip().replace('"', '')
    
    # === [关键修复] 立即更新数据库标题 ===
    if state.get("project_id"):
        try:
            update_project_title(state["project_id"], topic)
            logger.info(f"[{project_id}] 数据库标题已更新: {topic}")
        except Exception as e:
            logger.error(f"[{project_id}] 更新标题失败: {e}")
    # ===================================
    
    msg = f"💡 已自动生成主题：{topic}"
    return {"topic": topic, "run_logs": [msg]}

# 1. 分析师
async def analyst_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    project_id = state.get("project_id", "UNKNOWN")
    prompt = get_analyst_prompt(state["raw_content"], state["topic"])
    
    response = await invoke_with_logging(llm, [HumanMessage(content=prompt)], "Analyst", project_id)
    
    return {
        "topic_analysis": response,
        "run_logs": ["✅ [分析师] 素材提炼完成"]
    }

# 2. 架构师
async def architect_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    project_id = state.get("project_id", "UNKNOWN")
    # [修改] 获取字数，传入 prompt
    word_count = state.get("target_word_count", "1500字")
    
    prompt = get_architect_prompt(
        state["topic"], 
        state["topic_analysis"], 
        state["user_instruction"],
        word_count # <--- 传入
    )
    
    response = await invoke_with_logging(llm, [HumanMessage(content=prompt)], "Architect", project_id)
    
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        outline = json.loads(clean_json)
    except Exception as e:
        logger.error(f"[{project_id}] 大纲解析失败: {e}. AI Raw Response: {response}")
        outline = [{"title": "正文", "gist": "生成失败，请重试"}]
        
    return {
        "outline": outline,
        "current_section_index": 0,
        "section_drafts": [],
        "run_logs": [f"✅ [架构师] 生成 {len(outline)} 章大纲"]
    }

# 3. 撰稿人
async def writer_node(state: DeepWriteState) -> dict:
    idx = state["current_section_index"]
    outline = state["outline"]
    drafts = state["section_drafts"]
    project_id = state.get("project_id", "UNKNOWN")
    
    if idx >= len(outline): return {}

    current_sec = outline[idx]
    prev_context = "\n\n".join(drafts) if drafts else "(文章开头)"
    outline_str = json.dumps(outline, ensure_ascii=False, indent=1)
    
    llm = get_llm()
    prompt = get_writer_prompt(current_sec["title"], current_sec["gist"], prev_context, outline_str)
    
    # 日志：显示这一章的标题
    start_log = f"⏳ [撰稿人] 正在写第 {idx+1}/{len(outline)} 章: {current_sec['title']}"
    logger.info(f"[{project_id}] {start_log}")
    
    try:
        content = await invoke_with_logging(llm, [HumanMessage(content=prompt)], f"Writer-Ch{idx+1}", project_id)
        formatted_section = f"## {current_sec['title']}\n\n{content}"
        
        return {
            "section_drafts": [formatted_section],
            "current_section_index": idx + 1,
            "run_logs": [start_log, f"✅ 第 {idx+1} 章完成"]
        }
    except Exception:
        # 降级处理，防止中断
        return {
            "section_drafts": [f"## {current_sec['title']}\n\n(生成失败)"],
            "current_section_index": idx + 1,
            "run_logs": [start_log, f"❌ 第 {idx+1} 章失败，跳过"]
        }

# 4. 主编
async def reviewer_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    llm = get_llm()
    project_id = state.get("project_id", "UNKNOWN")
    prompt = get_reviewer_prompt(full_draft, state["user_instruction"])
    
    critique = await invoke_with_logging(llm, [HumanMessage(content=prompt)], "Reviewer", project_id)
    
    return {
        "critique_notes": critique,
        "run_logs": ["🧐 [主编] 审阅完成"]
    }

# 5. 润色师 (重点检查这里)
async def polisher_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    project_id = state.get("project_id")
    
    logger.info(f"✨ [润色师] 准备开始全文润色，输入长度: {len(full_draft)} 字符。")
    
    llm = get_llm()
    prompt = get_polisher_prompt(full_draft, state["critique_notes"])
    
    final_article = ""
    log_msg = ""

    try:
        final_article = await invoke_with_logging(llm, [HumanMessage(content=prompt)], "Polisher", project_id)
        log_msg = "✨ [润色师] 润色完成！"
    except Exception as e:
        logger.error(f"润色师超时或失败，降级为返回初稿: {e}")
        final_article = full_draft + "\n\n> (注：AI 润色阶段超时，已自动保存初稿)"
        log_msg = "⚠️ [润色师] 响应超时，已展示初稿"
    
    # === 关键修复：显式保存并打印日志 ===
    if project_id:
        logger.info(f"💾 [System] 正在执行最终归档... ID: {project_id}")
        try:
            update_project_draft(project_id, final_article)
            if state.get("outline"):
                update_project_outline(project_id, state["outline"])
        except Exception as db_e:
            logger.critical(f"❌ [System] 致命错误：最终归档失败！{db_e}", exc_info=True)
            log_msg += " (⚠️ 自动保存失败，请手动复制结果)"
    else:
        logger.error("❌ [System] 无法保存：State 中缺失 project_id")

    return {
        "final_article": final_article,
        "run_logs": [log_msg]
    }
