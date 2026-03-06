from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from src.graphs.write_graph_v3 import write_graph_v3
from src.state import DeepWriteState

router = APIRouter()

class WriteRequest(BaseModel):
    content: str
    topic: Optional[str] = "" # 变成可选
    instruction: str = "风格专业，逻辑清晰"

@router.post("/run")
async def run_write_v3(req: WriteRequest):
    """流式运行 DeepWrite V3 Graph"""
    
    # 初始化状态
    initial_state: DeepWriteState = {
        "topic": req.topic or "", # 空字符串，等待 TopicGen 生成
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
            # 维护一个累积的草稿，用于前端实时展示
            accumulated_drafts = [] 
            
            async for event in write_graph_v3.astream(initial_state):
                for node_name, update in event.items():
                    # 1. 提取日志
                    logs = update.get("run_logs", [])
                    
                    # 2. 提取并更新草稿内容
                    # 如果节点更新了 section_drafts (通常是 Writer 节点)
                    if "section_drafts" in update and update["section_drafts"]:
                        # 注意：langgraph 返回的是增量 update，还是全量取决于 reducer
                        # 在 state.py 我们用了 add_list，但 langgraph stream 返回的 update 字典通常只包含增量部分
                        # 所以我们把新的段落加到本地变量里
                        new_sections = update["section_drafts"]
                        accumulated_drafts.extend(new_sections)
                    
                    # 3. 构造当前可显示的全文
                    # 如果有 final_article 就用 final，否则用拼凑的草稿
                    current_display_text = update.get("final_article", "")
                    if not current_display_text:
                        current_display_text = "\n\n".join(accumulated_drafts)
                    
                    # 4. 提取主题（如果是 TopicGen 刚生成的）
                    current_topic = update.get("topic", "")

                    payload = {
                        "node": node_name,
                        "logs": logs,
                        "generated_topic": current_topic,
                        "display_content": current_display_text, # 统一发给前端
                        "is_final": bool(update.get("final_article"))
                    }
                    
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            print(f"Error in stream: {e}") # 打印到后台日志以便调试
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
