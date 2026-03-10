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

from pydantic import BaseModel
from src.db import delete_mastery_session

class AddConceptReq(BaseModel):
    session_id: str
    concept_name: str

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """【修复1】：删除学习记录"""
    try:
        delete_mastery_session(session_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add_concept")
async def add_custom_concept(req: AddConceptReq):
    """【修复3】：手动添加核心概念"""
    session = get_mastery_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    concepts = session["concepts_data"]
    # 防止重复
    if not any(c["name"] == req.concept_name for c in concepts):
        concepts.append({
            "name": req.concept_name,
            "axiom": "自定义添加的概念",
            "reason": "用户手动指定"
        })
        update_mastery_session_data(req.session_id, concepts)
    return {"status": "success", "concepts_data": concepts}

@router.post("/generate_more")
async def generate_more_concepts(session_id: str = Body(..., embed=True)):
    """【修复4】：联网生成更多概念"""
    session = get_mastery_session(session_id)
    if not session: raise HTTPException(404, "Not found")
    
    topic = session["topic"]
    existing_names = [c["name"] for c in session["concepts_data"]]
    
    # 强制搜索寻找新概念
    from src.tools.search import tavily_search
    from src.nodes.common import get_llm
    from langchain_core.messages import HumanMessage
    import json, re
    
    search_res = tavily_search(f"What are the advanced/niche core concepts of {topic}?", max_results=2)
    prompt = f"""
    主题：【{topic}】
    已经存在的概念：{existing_names}
    检索资料：{search_res}
    
    请根据资料，为该主题补充 2 个更深入、尚未提及的核心概念。
    严格返回 JSON List 格式:[{{"name": "...", "axiom": "...", "reason": "..."}}]
    """
    
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=prompt)]).content
    
    try:
        clean = response.replace("```json", "").replace("```", "").strip()
        new_concepts = json.loads(clean)
        if isinstance(new_concepts, list):
            session["concepts_data"].extend(new_concepts)
            update_mastery_session_data(session_id, session["concepts_data"])
    except:
        pass
        
    return {"status": "success", "concepts_data": session["concepts_data"]}

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
