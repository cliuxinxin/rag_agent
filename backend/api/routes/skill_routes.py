from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
import json
from src.skills.loader import SkillRegistry

router = APIRouter()
registry = SkillRegistry()

# 模块级延迟导入，避免循环引用
skill_graph = None

def get_skill_graph():
    global skill_graph
    if skill_graph is None:
        from src.graphs.skill_graph import skill_graph as graph
        skill_graph = graph
    return skill_graph

@router.get("/list")
async def list_available_skills():
    """获取所有可用工具/技能列表"""
    registry.refresh()
    return {"skills": registry.list_skills()}

@router.post("/stream")
async def skill_chat_stream(request: dict):
    """
    Skill Agent 流式对话接口
    """
    query = request.get("query")
    session_id = request.get("session_id", "skill_default")
    
    if not query:
        raise HTTPException(status_code=400, detail="Missing required field: query")
    
    # 构造初始状态
    initial_state = {
        "messages": [{"role": "user", "content": query}],
        "session_id": session_id,
    }
    
    async def event_generator():
        try:
            graph = get_skill_graph()
            async for step in graph.astream(initial_state, config={"recursion_limit": 50}):
                for node_name, update in step.items():
                    # 特殊处理 ToolMessage
                    event_data = {
                        "node": node_name,
                        "update": update,
                        "type": "progress"
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
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
            "X-Accel-Buffering": "no"
        }
    )
