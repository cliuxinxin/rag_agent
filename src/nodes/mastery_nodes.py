import json
import re
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.prompts import (
    get_mastery_extractor_prompt, 
    get_mastery_expander_prompt, 
    get_mastery_chat_prompt
)
from src.state import MasteryState
from src.tools.search import tavily_search
from src.logger import get_logger

logger = get_logger("Node_Mastery")

def robust_json_parse(raw_response: str, fallback_value):
    try:
        clean = raw_response.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        try:
            json_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', raw_response)
            if json_match:
                return json.loads(json_match.group(1))
        except Exception:
            pass
    return fallback_value

def extractor_node(state: MasteryState) -> dict:
    topic = state["topic"]
    logger.info(f"[Mastery] 开始提取核心概念: {topic}")
    
    # 【修复 4 & 5】：引入联网搜索
    search_context = ""
    try:
        logger.info(f"[Mastery] 正在联网搜索: {topic}")
        search_context = tavily_search(f"What is {topic} core concepts?", max_results=3)
    except Exception as e:
        logger.warning(f"[Mastery] 搜索失败: {e}")

    llm = get_llm()
    prompt = get_mastery_extractor_prompt(topic, search_context)
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    fallback_data =[{"name": f"关于 {topic} 的基础概念", "axiom": "请点击重试或自行添加", "reason": "解析或搜索失败"}]
    concepts = robust_json_parse(response, fallback_data)
    
    logger.info(f"[Mastery] 成功提取 {len(concepts)} 个概念")
    return {"core_concepts": concepts, "selected_concept": None, "concept_detail": ""}

def expander_node(state: MasteryState) -> dict:
    """阶段二：生成拓扑讲解"""
    topic = state["topic"]
    target = state["selected_concept"]
    logger.info(f"[Mastery] 正在展开概念: {target}")
    
    all_concepts = state.get("core_concepts", [])
    others_str = ", ".join([c['name'] for c in all_concepts if c['name'] != target])
    
    # 【核心修复】：为概念的深度解析进行二次"定向检索"
    search_context = ""
    try:
        logger.info(f"[Mastery] 正在为概念 {target} 进行二次定向检索...")
        # 将主题和细分概念组合进行精准搜索
        search_query = f"{topic} {target} 原理 机制 架构"
        search_context = tavily_search(search_query, max_results=3)
    except Exception as e:
        logger.warning(f"[Mastery] 二次定向检索失败: {e}")

    llm = get_llm()
    # 将搜索结果传入 Prompt
    prompt = get_mastery_expander_prompt(topic, target, others_str, search_context)
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    # 鲁棒解析兜底
    fallback_data = {
        "one_sentence_def": "解析失败，请尝试重新生成。",
        "analogy": "暂无",
        "core_logic": response, # 即使 JSON 失败，也把大模型的文本塞到这里显示
        "relationships":[],
        "derivations": [],
        "suggested_questions":[f"什么是{target}？", f"{target}有什么优势？", "请举个实际的例子"]
    }
    
    data = robust_json_parse(response, fallback_data)
    logger.info(f"[Mastery] 概念 {target} 展开完成")
    
    return {
        "concept_detail_data": data,
        "chat_history":[]
    }

def chat_node(state: MasteryState) -> dict:
    topic = state["topic"]
    concept = state["selected_concept"]
    history = state["chat_history"]
    logger.info(f"[Mastery] 用户发起追问, 概念: {concept}")
    
    last_msg = history[-1]
    hist_str = "\n".join([f"{m.type}: {m.content}" for m in history[:-1]]) if len(history) > 1 else "暂无"
    
    llm = get_llm()
    prompt = get_mastery_chat_prompt(topic, concept, hist_str, last_msg.content)
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {"chat_history": [response]}