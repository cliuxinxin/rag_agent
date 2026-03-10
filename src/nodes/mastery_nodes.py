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

# === 新增：强大的 JSON 提取器 ===
def robust_json_parse(raw_response: str, fallback_value):
    try:
        clean = raw_response.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        try:
            # 用正则强制提取大括号或中括号内的内容
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw_response)
            if json_match:
                return json.loads(json_match.group(1))
        except Exception:
            pass
    return fallback_value

def extractor_node(state: MasteryState) -> dict:
    """阶段一：提取核心 20%"""
    topic = state["topic"]
    llm = get_llm()
    
    prompt = get_mastery_extractor_prompt(topic)
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    # 【修复】使用鲁棒解析
    fallback_data =[{"name": "解析失败", "axiom": "请重试", "reason": "大模型返回格式错误"}]
    concepts = robust_json_parse(response, fallback_data)
        
    return {
        "core_concepts": concepts,
        "selected_concept": None,
        "concept_detail": ""
    }

def expander_node(state: MasteryState) -> dict:
    """阶段二：生成拓扑讲解"""
    topic = state["topic"]
    target = state["selected_concept"]
    all_concepts = state.get("core_concepts",[])
    
    others_str = ", ".join([c['name'] for c in all_concepts if c['name'] != target])
    
    llm = get_llm()
    prompt = get_mastery_expander_prompt(topic, target, others_str)
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    # 【修复】使用鲁棒解析
    fallback_data = {
        "one_sentence_def": "解析失败，请重试。",
        "analogy": "无",
        "core_logic": response, # 就算失败，也把原文塞进核心逻辑里给用户看
        "relationships": [],
        "derivations": [],
        "suggested_questions":["这个概念的核心是什么？", "请举个例子"]
    }
    
    data = robust_json_parse(response, fallback_data)
    
    return {
        "concept_detail_data": data,
        "chat_history":[] 
    }

def chat_node(state: MasteryState) -> dict:
    """阶段三：针对性问答"""
    topic = state["topic"]
    concept = state["selected_concept"]
    history = state["chat_history"]
    
    last_msg = history[-1]
    
    # 【修复】防止 history[:-1] 越界或拼接异常
    hist_str = ""
    if len(history) > 1:
        hist_str = "\n".join([f"{m.type}: {m.content}" for m in history[:-1]])
    else:
        hist_str = "暂无历史对话"
    
    llm = get_llm()
    prompt = get_mastery_chat_prompt(topic, concept, hist_str, last_msg.content)
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {"chat_history": [response]}