from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from src.graphs.copilot_graph import copilot_init_graph, copilot_chat_graph
from src.db import (
    get_all_copilot_sessions,
    get_copilot_session,
    get_copilot_messages,
    add_copilot_message,
    delete_copilot_session,
    STORAGE_DIR
)
from src.nodes.common import get_llm
from src.logger import get_logger
llm_stream = get_llm().with_config({"streaming": True})
from fastapi.responses import StreamingResponse
import json
from pathlib import Path

logger = get_logger("CopilotRoutes")

router = APIRouter(tags=["copilot"])

# ==============================
# 请求模型
# ==============================

class InitRequest(BaseModel):
    raw_text: str

class ChatRequest(BaseModel):
    session_id: str
    query: Optional[str] = ""
    quote_text: Optional[str] = ""
    action: str = "question"  # explain/translate/summarize/question

# ==============================
# 接口实现
# ==============================

@router.post("/init")
async def init_copilot(request: InitRequest):
    """初始化长文伴读，接收原始文本，返回session_id"""
    try:
        if not request.raw_text or len(request.raw_text.strip()) == 0:
            raise HTTPException(status_code=400, detail="文本不能为空")
        
        logger.info(f"开始初始化长文伴读，文本长度：{len(request.raw_text)}")
        
        # 执行初始化工作流
        initial_state = {
            "raw_text": request.raw_text
        }
        logger.debug("开始执行copilot_init_graph")
        result = await copilot_init_graph.ainvoke(initial_state)
        logger.info(f"长文伴读初始化成功，session_id: {result['session_id']}")
        
        return {
            "success": True,
            "session_id": result["session_id"]
        }
    except Exception as e:
        logger.error(f"长文伴读初始化失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")

@router.get("/sessions")
async def get_sessions():
    """获取所有历史阅读项目列表"""
    try:
        sessions = get_all_copilot_sessions()
        return {
            "success": True,
            "data": sessions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取单篇文章详情"""
    try:
        session = get_copilot_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 读取Markdown文件内容
        md_path = STORAGE_DIR / f"copilot_{session_id}.md"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail="文章内容不存在")
        
        with open(md_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 获取对话历史
        messages = get_copilot_messages(session_id)
        
        return {
            "success": True,
            "data": {
                **session,
                "markdown_content": markdown_content,
                "messages": messages
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口"""
    try:
        session = get_copilot_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 保存用户消息
        add_copilot_message(
            session_id=request.session_id,
            role="user",
            content=request.query,
            quote_text=request.quote_text
        )
        
        # 执行对话工作流获取上下文
        state = {
            "session_id": request.session_id,
            "user_query": request.query,
            "selected_text": request.quote_text,
            "action": request.action
        }
        result = await copilot_chat_graph.ainvoke(state)
        response_content = result["response"]
        
        # 保存助手消息
        add_copilot_message(
            session_id=request.session_id,
            role="assistant",
            content=response_content,
            quote_text=request.quote_text
        )
        
        # 流式输出
        async def generate():
            for chunk in response_content:
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    try:
        delete_copilot_session(session_id)
        return {
            "success": True,
            "message": "删除成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")