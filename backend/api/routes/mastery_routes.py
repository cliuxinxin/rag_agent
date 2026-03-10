from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Optional
from src.nodes.mastery_nodes import extractor_node, expander_node, chat_node
from src.db import (
    create_mastery_session, 
    get_mastery_session, 
    update_mastery_concepts, 
    get_all_mastery_sessions, 
    update_mastery_session_data
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import json

router = APIRouter()

def serialize_message(msg: BaseMessage) -> dict:
    return {"role": "user" if isinstance(msg, HumanMessage) else "assistant", "content": msg.content}

def deserialize_message(msg_dict: dict) -> BaseMessage:
    if msg_dict["role"] == "user":
        return HumanMessage(content=msg_dict["content"])
    return AIMessage(content=msg_dict["content"])

@router.post("/session")
async def create_session(topic: str = Body(..., embed=True)):
    """创建新的学习会话"""
    try:
        session_id = create_mastery_session(topic)
        # 初始提取核心概念
        result = extractor_node({"topic": topic})
        core_concepts = result["core_concepts"]
        # 保存初始概念
        update_mastery_session_data(session_id, core_concepts)
        return {"session_id": session_id, "topic": topic, "core_concepts": core_concepts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions")
async def list_sessions():
    """获取所有学习记录"""
    return {"sessions": get_all_mastery_sessions()}

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取特定会话详情"""
    session = get_mastery_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/expand")
async def expand_concept(
    session_id: str = Body(...),
    concept_name: str = Body(...),
    topic: str = Body(...)
):
    """展开某个核心概念的底层逻辑"""
    session = get_mastery_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 构造 expander_node 需要的状态
    state = {
        "topic": topic,
        "selected_concept": concept_name
    }
    
    try:
        res = expander_node(state)
        detail_data = res["concept_detail_data"]
        
        # 更新数据库中的概念详情
        concepts = session["concepts_data"]
        for c in concepts:
            if c["name"] == concept_name:
                c["detail"] = detail_data
                c["chat_history"] = [] # 初始化聊天记录
                break
        
        update_mastery_session_data(session_id, concepts)
        return {"detail": detail_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def mastery_chat(
    session_id: str = Body(...),
    concept_name: str = Body(...),
    topic: str = Body(...),
    message: str = Body(...)
):
    """针对特定概念的深度对话"""
    session = get_mastery_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    concepts = session["concepts_data"]
    concept = next((c for c in concepts if c["name"] == concept_name), None)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    # 恢复聊天记录
    history_dicts = concept.get("chat_history", [])
    history = [deserialize_message(m) for m in history_dicts]
    history.append(HumanMessage(content=message))
    
    state = {
        "topic": topic,
        "selected_concept": concept_name,
        "chat_history": history
    }
    
    try:
        res = chat_node(state)
        # res["chat_history"] 里只有 LLM 这次的新回答
        ai_msg = res["chat_history"][-1] 
        
        # 【核心修复】将 AI 的回复追加到完整历史列表中
        history.append(ai_msg)
        
        # 把完整的 history 序列化并存入 concept
        concept["chat_history"] = [serialize_message(m) for m in history]
        update_mastery_session_data(session_id, concepts)
        
        return {"reply": ai_msg.content, "history": concept["chat_history"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
