# src/nodes/mastery_nodes.py
import json
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.nodes.common import get_llm
from src.prompts import (
    get_mastery_extractor_prompt, 
    get_mastery_expander_prompt, 
    get_mastery_chat_prompt
)
from src.state import MasteryState


def extractor_node(state: MasteryState) -> dict:
    """阶段一：提取核心 20%"""
    topic = state["topic"]
    llm = get_llm()
    
    prompt = get_mastery_extractor_prompt(topic)
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    try:
        # 清洗 JSON
        clean_json = response.replace("```json", "").replace("```", "").strip()
        concepts = json.loads(clean_json)
    except:
        # Fallback
        concepts = [{"name": "解析失败", "axiom": "请重试", "reason": "格式错误"}]
        
    return {
        "core_concepts": concepts,
        "selected_concept": None, # 重置选中
        "concept_detail": ""
    }


def expander_node(state: MasteryState) -> dict:
    """阶段二：生成拓扑讲解"""
    topic = state["topic"]
    target = state["selected_concept"]
    all_concepts = state.get("core_concepts", [])
    
    # 构造上下文：把所有核心概念名字告诉 LLM，方便它找关系
    others_str = ", ".join([c['name'] for c in all_concepts if c['name'] != target])
    
    llm = get_llm()
    prompt = get_mastery_expander_prompt(topic, target, others_str)
    
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    try:
        # 尝试解析 JSON
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
    except:
        # Fallback 数据
        data = {
            "one_sentence_def": "解析失败，请重试。",
            "analogy": "无",
            "core_logic": response, # 把原文放进去
            "relationships": [],
            "derivations": [],
            "suggested_questions": ["这个概念的核心是什么？", "它有什么应用场景？", "请举个例子"]
        }
    
    # 这里我们只返回 data，View 层负责渲染
    # 同时初始化聊天记录，不再需要欢迎语，直接空着即可
    return {
        "concept_detail_data": data, # 临时传递给 View
        "chat_history": [] 
    }


def chat_node(state: MasteryState) -> dict:
    """阶段三：针对性问答"""
    topic = state["topic"]
    concept = state["selected_concept"]
    history = state["chat_history"]
    # 取最后一条作为 User Input
    last_msg = history[-1]
    
    # 将 History 转为 string 供 Prompt 参考
    hist_str = "\n".join([f"{m.type}: {m.content}" for m in history[:-1]])
    
    llm = get_llm()
    prompt = get_mastery_chat_prompt(topic, concept, hist_str, last_msg.content)
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {"chat_history": [response]} # 增量更新 (add_messages 处理)