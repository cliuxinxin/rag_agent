from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
import json
from src.graphs.deep_qa_graph import deep_qa_graph
from src.storage import load_kbs
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

router = APIRouter()

def serialize_message(msg: BaseMessage) -> dict:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    return {"role": role, "content": msg.content}

@router.post("/stream")
async def deep_qa_stream(request: dict):
    """
    深度追问流式接口
    """
    query = request.get("query")
    session_id = request.get("session_id", "qa_default")
    kb_names = request.get("kb_names", [])
    history = request.get("history", []) # 之前的问答对
    
    if not query:
        raise HTTPException(status_code=400, detail="Missing required field: query")
    
    # 加载知识库
    source_documents, vector_store = load_kbs(kb_names)
    
    # 构造初始状态
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "source_documents": source_documents,
        "vector_store": vector_store,
        "next": "QAPlanner", # 根据图定义，入口是 QAPlanner
        "current_search_query": "",
        "final_evidence": [],
        "loop_count": 0,
        "attempted_searches": [],
        "research_notes": [],
        "failed_topics": [],
        "full_content": "",
        "doc_title": "",
        "current_question": query,
        "qa_pairs": history,
        "final_report": ""
    }
    
    async def event_generator():
        try:
            # 使用 astream 处理异步流
            async for step in deep_qa_graph.astream(initial_state, config={"recursion_limit": 50}):
                for node_name, update in step.items():
                    # 将节点更新包装成 SSE 格式
                    event_data = {
                        "node": node_name,
                        "update": update,
                        "type": "progress"
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False, default=str)}\n\n"
            
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
