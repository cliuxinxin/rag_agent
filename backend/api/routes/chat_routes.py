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
        from src.db import get_messages
        messages = get_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败：{str(e)}")


@router.post("/sessions", summary="创建新会话")
async def create_new_session(title: str = Query(...), mode: str = Query("chat")):
    """
    创建新的对话会话
    """
    try:
        from src.db import create_session as db_create_session
        session_id = db_create_session(title, mode)
        return {"session_id": session_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败：{str(e)}")


@router.post("/sessions/{session_id}/generate_title", summary="智能生成并更新会话标题")
async def generate_session_title(session_id: str):
    """
    根据会话的第一轮对话，自动生成简短标题并更新数据库。
    """
    try:
        from src.db import get_messages, update_session_title
        from src.nodes.common import get_llm
        from langchain_core.messages import HumanMessage
        
        messages = get_messages(session_id)
        if not messages or len(messages) < 2:
            return {"status": "skipped", "reason": "Not enough messages"}
            
        user_query = messages[0]['content']
        ai_response = messages[1]['content']
        
        llm = get_llm()
        prompt = f"""
        请根据以下对话内容，为一个聊天会话起一个极其简短的标题（不超过 10 个字）。
        只需输出标题文字，不要有任何标点符号或前缀。
        
        用户：{user_query}
        助手：{ai_response[:200]}...
        """
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        smart_title = response.content.strip().replace('"', '').replace("'", "")
        
        update_session_title(session_id, smart_title)
        return {"status": "updated", "title": smart_title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成标题失败：{str(e)}")


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(session_id: str):
    """删除指定会话及其所有消息"""
    try:
        from src.db import delete_session as db_delete_session
        db_delete_session(session_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败：{str(e)}")
