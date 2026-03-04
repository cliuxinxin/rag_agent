"""
聊天相关 API 路由
提供流式对话、历史消息等功能
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import json

# 模块级延迟导入，避免循环引用
chat_graph = None

def get_chat_graph():
    global chat_graph
    if chat_graph is None:
        from src.graphs.chat_graph import chat_graph as graph
        chat_graph = graph
    return chat_graph

router = APIRouter()


@router.post("/stream", summary="流式聊天接口")
async def chat_stream(request: dict):
    """
    流式聊天接口 (SSE - Server-Sent Events)
    
    **请求体:**
    ```json
    {
        "query": "用户问题",
        "session_id": "会话 ID (可选)",
        "kb_ids": [1, 2, 3] (可选，使用的知识库 ID 列表),
        "mode": "chat|deep_qa" (可选，对话模式)
    }
    ```
    
    **响应:** SSE 流，包含节点执行进度和最终结果
    
    **SSE 事件格式:**
    - `progress`: 节点执行进度
    - `done`: 完成信号
    - `error`: 错误信息
    """
    query = request.get("query")
    session_id = request.get("session_id", "default")
    kb_ids = request.get("kb_ids", [])
    mode = request.get("mode", "chat")
    
    if not query:
        raise HTTPException(status_code=400, detail="Missing required field: query")
    
    # 构造初始状态 (参考原 chat.py 逻辑)
    initial_state = {
        "messages": [{"role": "user", "content": query}],
        "next": "Supervisor",
        "session_id": session_id,
        "kb_ids": kb_ids,
        "mode": mode,
    }
    
    # 延迟导入 db 函数
    from src.db import get_messages, create_session
    
    async def event_generator():
        """SSE 事件生成器"""
        try:
            # 调用 LangGraph 的流式处理
            graph = get_chat_graph()
            for step in graph.stream(initial_state, config={"recursion_limit": 50}):
                for node_name, update in step.items():
                    # 将节点更新包装成 SSE 格式
                    event_data = {
                        "node": node_name,
                        "update": str(update) if not isinstance(update, dict) else update,
                        "type": "progress"
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
            # 发送完成信号
            yield "data: {\"type\": \"done\"}\n\n"
            
        except Exception as e:
            error_data = {
                "type": "error",
                "message": str(e),
                "node": "system"
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 缓冲禁用
        }
    )


@router.get("/sessions/{session_id}/messages", summary="获取会话消息历史")
async def get_session_messages(session_id: str):
    """
    获取指定会话的所有消息历史
    
    **路径参数:**
    - `session_id`: 会话 ID
    
    **返回:** 消息列表，包含角色和内容
    """
    try:
        messages = get_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败：{str(e)}")


@router.post("/sessions", summary="创建新会话")
async def create_new_session(title: str = Query(...), mode: str = Query("chat")):
    """
    创建新的对话会话
    
    **查询参数:**
    - `title`: 会话标题
    - `mode`: 会话模式 (chat|deep_qa|deep_read|...)
    
    **返回:** 新建的会话 ID
    """
    try:
        session_id = create_session(title, mode)
        return {"session_id": session_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败：{str(e)}")
