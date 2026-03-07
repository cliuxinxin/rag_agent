import json
import time
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.state import DeepWriteState
from src.logger import get_logger
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

# === 辅助函数：带详细日志的 LLM 调用 ===
def invoke_with_logging(llm, messages, stage_name: str) -> str:
    """
    封装 LLM 调用，记录详细的输入输出日志和耗时
    """
    start_time = time.time()
    
    # 1. 记录输入 (Prompt)
    # 提取最后一条 User Message 的内容进行预览
    last_msg = messages[-1].content
    preview_len = 500
    prompt_preview = last_msg[:preview_len] + "..." if len(last_msg) > preview_len else last_msg
    
    logger.info(f"🚀 [{stage_name}] 请求发送给 AI...")
    logger.info(f"📝 [{stage_name}] Prompt 预览 (前 {preview_len} 字符):\n{prompt_preview}\n{'-'*30}")
    
    try:
        # 2. 执行调用
        response = llm.invoke(messages)
        content = response.content
        
        # 3. 记录耗时与输出
        duration = time.time() - start_time
        logger.info(f"✅ [{stage_name}] AI 响应成功 | 耗时: {duration:.2f}s | 输出长度: {len(content)} 字符")
        
        return content
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ [{stage_name}] AI 调用失败 | 耗时: {duration:.2f}s | 错误: {str(e)}", exc_info=True)
        raise e

# === 节点定义 ===

# 0. 主题生成
def topic_generator_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    content = state.get("raw_content") or "无内容"
    
    logger.info("🎬 [TopicGen] 开始工作...")
    prompt = get_topic_gen_prompt(content)
    
    topic = invoke_with_logging(llm, [HumanMessage(content=prompt)], "TopicGen").strip().replace('"', '')
    
    # === [关键修复] 立即更新数据库标题 ===
    if state.get("project_id"):
        try:
            update_project_title(state["project_id"], topic)
            logger.info(f"数据库标题已更新: {topic}")
        except Exception as e:
            logger.error(f"更新标题失败: {e}")
    # ===================================
    
    msg = f"💡 已自动生成主题：{topic}"
    return {"topic": topic, "run_logs": [msg]}

# 1. 分析师
def analyst_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    prompt = get_analyst_prompt(state["raw_content"], state["topic"])
    
    response = invoke_with_logging(llm, [HumanMessage(content=prompt)], "Analyst")
    
    return {
        "topic_analysis": response,
        "run_logs": ["✅ [分析师] 素材提炼完成"]
    }

# 2. 架构师
def architect_node(state: DeepWriteState) -> dict:
    llm = get_llm()
    prompt = get_architect_prompt(state["topic"], state["topic_analysis"], state["user_instruction"])
    
    response = invoke_with_logging(llm, [HumanMessage(content=prompt)], "Architect")
    
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        outline = json.loads(clean_json)
    except Exception as e:
        logger.error(f"大纲解析失败: {e}. AI Raw Response: {response}")
        outline = [{"title": "正文", "gist": "生成失败，请重试"}]
        
    return {
        "outline": outline,
        "current_section_index": 0,
        "section_drafts": [],
        "run_logs": [f"✅ [架构师] 生成 {len(outline)} 章大纲"]
    }

# 3. 撰稿人
def writer_node(state: DeepWriteState) -> dict:
    idx = state["current_section_index"]
    outline = state["outline"]
    drafts = state["section_drafts"]
    
    if idx >= len(outline): return {}

    current_sec = outline[idx]
    prev_context = "\n\n".join(drafts) if drafts else "(文章开头)"
    outline_str = json.dumps(outline, ensure_ascii=False, indent=1)
    
    llm = get_llm()
    prompt = get_writer_prompt(current_sec["title"], current_sec["gist"], prev_context, outline_str)
    
    # 日志：显示这一章的标题
    start_log = f"⏳ [撰稿人] 正在写第 {idx+1}/{len(outline)} 章: {current_sec['title']}"
    logger.info(start_log)
    
    try:
        content = invoke_with_logging(llm, [HumanMessage(content=prompt)], f"Writer-Ch{idx+1}")
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
def reviewer_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    llm = get_llm()
    prompt = get_reviewer_prompt(full_draft, state["user_instruction"])
    
    critique = invoke_with_logging(llm, [HumanMessage(content=prompt)], "Reviewer")
    
    return {
        "critique_notes": critique,
        "run_logs": ["🧐 [主编] 审阅完成"]
    }

# 5. 润色师 (最容易超时的地方)
def polisher_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    
    logger.info(f"✨ [润色师] 准备开始全文润色，输入长度: {len(full_draft)} 字符。这可能需要较长时间...")
    
    llm = get_llm()
    prompt = get_polisher_prompt(full_draft, state["critique_notes"])
    
    # 润色师如果超时，我们做一个兜底：直接返回初稿，不让用户觉得失败了
    try:
        final_article = invoke_with_logging(llm, [HumanMessage(content=prompt)], "Polisher")
        log_msg = "✨ [润色师] 润色完成！"
    except Exception as e:
        logger.error(f"润色师超时或失败，降级为返回初稿: {e}")
        final_article = full_draft + "\n\n> (注：由于篇幅过长，AI 润色超时，以上为初稿内容)"
        log_msg = "⚠️ [润色师] 响应超时，已展示初稿"
    
    # 保存到数据库
    if state.get("project_id"):
        update_project_draft(state["project_id"], final_article)
        if state.get("outline"):
            update_project_outline(state["project_id"], state["outline"])

    return {
        "final_article": final_article,
        "run_logs": [log_msg]
    }
