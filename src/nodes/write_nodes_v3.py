import json
import time
import datetime
import re
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.state import DeepWriteState
from src.logger import get_logger, log_llm_trace
from src.db import update_project_draft, update_project_outline, update_project_title, update_project_process_data, append_project_log
from src.prompts_v3 import (
    get_angle_proposal_prompt,
    get_title_gen_prompt,
    get_topic_gen_prompt,
    get_analyst_prompt,
    get_architect_prompt,
    get_writer_prompt,
    get_reviewer_prompt,
    get_polisher_prompt
)

logger = get_logger("DeepWrite_V3")

# === 通用鲁棒JSON解析函数 ===
def robust_json_parse(raw_response: str, fallback_value):
    """
    鲁棒解析JSON，支持带markdown标记的响应、格式不完整的JSON等情况
    """
    try:
        # 第一步：先尝试简单清洗
        clean = raw_response.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        try:
            # 第二步：用正则提取JSON块
            json_match = re.search(r'(\{.*\}|\[.*\])', raw_response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except Exception:
            try:
                # 第三步：尝试修复常见JSON格式错误（如缺少引号、尾随逗号等）
                # 移除尾随逗号
                fixed = re.sub(r',\s*([}\]])', r'\1', raw_response)
                # 尝试解析
                return json.loads(fixed)
            except Exception as e:
                logger.warning(f"JSON解析失败，使用降级值: {e}")
                return fallback_value

# === 增强版日志记录 ===
async def invoke_with_logging(llm, messages, stage_name: str, project_id: str = "N/A") -> str:
    """
    封装 LLM 异步调用，记录详细的输入输出日志和耗时，支持 project_id 链路追踪
    """
    start_time = time.time()
    
    # 构造 Prompt 文本用于记录
    prompt_content = "\n".join([m.content for m in messages])
    
    logger.info(f"[{project_id}] 🚀 [{stage_name}] 请求 LLM (Input: {len(prompt_content)} chars)")
    
    try:
        # 执行异步调用
        response = await llm.ainvoke(messages)
        content = response.content
        duration = time.time() - start_time
        
        # 1. 记录简要日志到 app.log
        logger.info(f"[{project_id}] ✅ [{stage_name}] 完成 | {duration:.2f}s | Output: {len(content)} chars")
        
        # 2. 记录详细日志到 llm_trace.log (方便调试和优化 Prompt)
        log_llm_trace(f"{project_id}::{stage_name}", prompt_content, content, duration)
        
        # 3. 保存到数据库的详细日志
        if project_id and project_id != "N/A":
            log_entry = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stage": stage_name,
                "duration": f"{duration:.2f}s",
                "input_prompt_preview": prompt_content[:500] + "..." if len(prompt_content) > 500 else prompt_content,
                "full_input_prompt": prompt_content,  # 完整保存方便调试
                "output_response": content
            }
            try:
                append_project_log(project_id, log_entry)
            except Exception as log_err:
                logger.warning(f"日志存储失败: {log_err}")
        
        return content
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{project_id}] ❌ [{stage_name}] 失败 | {duration:.2f}s | Err: {e}")
        raise e

# === 节点定义 ===

# [新增] 1. 角度策划节点 (新起点)
async def angle_proposer_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    project_id = state.get("project_id", "N/A")
    
    prompt = get_angle_proposal_prompt(state["raw_content"], state["user_instruction"])
    
    response = await invoke_with_logging(llm, [HumanMessage(content=prompt)], "AngleProposer", project_id)
    
    # 使用鲁棒JSON解析
    fallback_angles = [{"id": "A", "label": "默认方向", "description": "解析失败，使用默认分析模式", "pros": "默认"}]
    angles = robust_json_parse(response, fallback_angles)
    
    # 存入数据库 process_data
    if project_id and project_id != "N/A":
        try:
            update_project_process_data(project_id, {"proposed_angles": angles})
        except Exception as e:
            logger.warning(f"过程数据保存失败: {e}")
        
    return {
        "angles_options": angles,
        "run_logs": ["✅ 已生成 3 个切入方向，等待用户选择..."]
    }

# [新增] 2. 标题与大纲生成 (合并步骤)
async def structure_gen_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    project_id = state.get("project_id", "N/A")
    
    # 获取用户选的角度
    selected_angle = state.get("selected_angle_data", {})
    angle_desc = selected_angle.get("description", "综合分析")
    
    # 1. 生成标题
    title_prompt = get_title_gen_prompt(state["raw_content"], angle_desc)
    topic = (await invoke_with_logging(llm, [HumanMessage(content=title_prompt)], "TitleGen", project_id)).strip().replace('"', '')
    
    if project_id and project_id != "N/A":
        try:
            update_project_title(project_id, topic)
        except Exception as e:
            logger.warning(f"标题保存失败: {e}")

    # 2. 分析素材
    analyst_prompt = get_analyst_prompt(state["raw_content"], topic)
    analysis = await invoke_with_logging(llm, [HumanMessage(content=analyst_prompt)], "Analyst", project_id)
    
    # 3. 生成大纲
    word_count = state.get("target_word_count", "1500")
    architect_prompt = get_architect_prompt(topic, analysis, state["user_instruction"], word_count)
    outline_resp = await invoke_with_logging(llm, [HumanMessage(content=architect_prompt)], "Architect", project_id)
    
    # 使用鲁棒JSON解析
    fallback_outline = [{"title": "正文", "gist": "生成失败，请重试"}]
    outline = robust_json_parse(outline_resp, fallback_outline)
        
    if project_id and project_id != "N/A":
        try:
            update_project_outline(project_id, outline)
        except Exception as e:
            logger.warning(f"大纲保存失败: {e}")

    return {
        "topic": topic,
        "topic_analysis": analysis,
        "outline": outline,
        "current_section_index": 0,
        "section_drafts": [],
        "run_logs": [f"✅ 标题确立：{topic}", f"✅ 大纲架构已完成 ({len(outline)} 章)"]
    }

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
    
    # 使用鲁棒JSON解析
    fallback_outline = [{"title": "正文", "gist": "生成失败，请重试"}]
    outline = robust_json_parse(response, fallback_outline)
        
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
    section_drafts = state["section_drafts"]
    project_id = state.get("project_id")
    critique_notes = state.get("critique_notes", "")
    
    logger.info(f"✨ [润色师] 准备开始分段润色，共 {len(section_drafts)} 个章节。")
    
    llm = get_llm()
    polished_sections = []
    previous_context = ""
    log_msg = ""
    full_draft = "\n\n".join(section_drafts)
    
    # 检查全文长度，如果过短则直接全文润色，过长则分段润色
    try:
        if len(full_draft) < 4000:
            # 短文章直接全文润色
            logger.info(f"📝 文章长度 {len(full_draft)} 字符，采用全文润色模式")
            prompt = get_polisher_prompt(full_draft, critique_notes)
            final_article = await invoke_with_logging(llm, [HumanMessage(content=prompt)], "Polisher-Full", project_id)
            log_msg = "✨ [润色师] 全文润色完成！"
        else:
            # 长文章分段润色，保持上下文连贯
            logger.info(f"📝 文章长度 {len(full_draft)} 字符，采用分段润色模式")
            for idx, section in enumerate(section_drafts):
                logger.info(f"⏳ 正在润色第 {idx+1}/{len(section_drafts)} 章")
                # 润色当前章节，带上前文上下文和总评审意见
                prompt = f"""
请根据以下评审意见润色当前章节，保持与前文的连贯性和整体风格一致：

【总评审意见】：{critique_notes}

【前文内容摘要】：{previous_context[-1000:] if previous_context else "无前文"}

【当前章节原文】：
{section}

请直接输出润色后的章节内容，不需要额外解释：
"""
                polished_section = await invoke_with_logging(llm, [HumanMessage(content=prompt)], f"Polisher-Ch{idx+1}", project_id)
                polished_sections.append(polished_section)
                # 更新上下文，用于下一章润色
                previous_context += polished_section + "\n\n"
            
            final_article = "\n\n".join(polished_sections)
            log_msg = "✨ [润色师] 分段润色完成！"
            
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

# === 控制流函数 ===

def check_continue(state: DeepWriteState):
    """
    决定是否继续写作或进入评审阶段
    """
    idx = state.get("current_section_index", 0)
    outline = state.get("outline", [])
    
    if idx >= len(outline):
        # 所有章节都写完了，进入评审
        if state.get("fast_mode"):
            return "FastFinish"
        else:
            return "Reviewer"
    else:
        # 继续写下一章
        return "Writer"

# 极速模式完成节点
async def fast_finish_node(state: DeepWriteState) -> dict:
    """
    极速模式下，跳过评审和润色，直接返回初稿
    """
    final_article = "\n\n".join(state.get("section_drafts", []))
    project_id = state.get("project_id", "UNKNOWN")
    
    if project_id and project_id != "N/A":
        try:
            update_project_draft(project_id, final_article)
        except Exception as e:
            logger.warning(f"极速模式草稿保存失败: {e}")
    
    return {
        "final_article": final_article,
        "run_logs": ["⚡ [极速模式] 直接发布初稿"]
    }
