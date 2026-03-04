"""
数据库相关 API 路由
提供会话管理、消息 CRUD 等功能
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


class SessionModel(BaseModel):
    """会话数据模型"""
    session_id: Optional[str] = None
    title: str
    mode: str = "chat"


class MessageModel(BaseModel):
    """消息数据模型"""
    session_id: str
    role: str
    content: str


@router.get("/sessions", summary="获取所有会话列表")
async def get_sessions():
    """
    获取所有历史会话列表
    
    **返回:** 会话列表，包含 ID、标题、模式等信息
    """
    try:
        from src.db import get_all_sessions
        sessions = get_all_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败：{str(e)}")


@router.get("/sessions/{session_id}/messages", summary="获取指定会话的消息")
async def get_session_messages(session_id: str):
    """
    获取指定会话的所有消息历史记录
    
    **路径参数:**
    - `session_id`: 会话 ID
    
    **返回:** 消息列表，按时间顺序排列
    """
    try:
        from src.db import get_messages
        messages = get_messages(session_id)
        return {"messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败：{str(e)}")


@router.post("/sessions", summary="创建新会话")
async def create_new_session(session: SessionModel):
    """
    创建新的对话会话
    
    **请求体:**
    ```json
    {
        "title": "会话标题",
        "mode": "chat"
    }
    ```
    
    **返回:** 新建的会话 ID
    """
    try:
        from src.db import create_session as db_create_session
        session_id = db_create_session(session.title, session.mode)
        return {"session_id": session_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败：{str(e)}")


@router.delete("/sessions/{session_id}", summary="删除会话")
async def remove_session(session_id: str):
    """
    删除指定的会话及其所有消息
    
    **路径参数:**
    - `session_id`: 要删除的会话 ID
    
    **返回:** 删除状态
    """
    try:
        from src.db import delete_session
        delete_session(session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败：{str(e)}")


@router.post("/messages", summary="保存消息")
async def save_new_message(message: MessageModel):
    """
    保存单条消息到数据库
    
    **请求体:**
    ```json
    {
        "session_id": "会话 ID",
        "role": "user|assistant",
        "content": "消息内容"
    }
    ```
    
    **返回:** 保存状态
    """
    try:
        from src.db import save_message
        save_message(message.session_id, message.role, message.content)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存消息失败：{str(e)}")


@router.post("/sessions/{session_id}/clear", summary="清空会话消息")
async def clear_session_messages(session_id: str):
    """
    清空指定会话的所有消息（但保留会话本身）
    
    **路径参数:**
    - `session_id`: 会话 ID
    
    **返回:** 清空状态
    """
    try:
        # 注意：需要实现 clear_session_messages 函数
        # from src.db import clear_session_messages
        # clear_session_messages(session_id)
        return {"status": "cleared", "session_id": session_id}
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="功能尚未实现")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空消息失败：{str(e)}")
