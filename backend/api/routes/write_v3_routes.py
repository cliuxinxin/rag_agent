from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import uuid
from src.graphs.write_graph_v3 import write_graph_v3
from src.state import DeepWriteState

router = APIRouter()

class WriteRequest(BaseModel):
    topic: str
    content: str
    instruction: str = "风格专业，逻辑清晰"

@router.post("/run")
async def run_write_v3(req: WriteRequest):
    """流式运行 DeepWrite V3 Graph"""
    
    # 初始化状态
    initial_state: DeepWriteState = {
        "topic": req.topic,
        "raw_content": req.content,
        "user_instruction": req.instruction,
        "topic_analysis": "",
        "outline": [],
        "current_section_index": 0,
        "section_drafts": [],
        "critique_notes": "",
        "final_article": "",
        "run_logs": []
    }
    
    async def event_generator():
        try:
            # 使用 astream (异步流)
            async for event in write_graph_v3.astream(initial_state):
                for node_name, update in event.items():
                    # 提取日志
                    logs = update.get("run_logs", [])
                    
                    # 构造发送给前端的数据
                    payload = {
                        "node": node_name,
                        "logs": logs,
                        "final_article": update.get("final_article", ""),
                        "outline": update.get("outline", [])
                    }
                    
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")