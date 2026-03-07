from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Union
import json
import uuid
from src.graphs.write_graph_v3 import write_graph_v3
from src.state import DeepWriteState
from src.logger import get_logger
from src.db import create_writing_project

logger = get_logger("API_WriteV3")

router = APIRouter()

# === 核心修复：更宽容的请求模型 ===
class WriteRequest(BaseModel):
    content: str = Field(..., description="原始素材")
    # 允许 topic 为空，或不传
    topic: Optional[str] = Field(default="", description="主题")
    instruction: str = Field(default="风格专业，逻辑清晰", description="要求")
    fast_mode: bool = Field(default=False, description="极速模式")
    # 允许 word_count 传字符串或数字，自动兼容
    word_count: Union[str, int] = Field(default="1500", description="字数")

@router.post("/run")
async def run_write_v3(req: WriteRequest):
    """流式运行 DeepWrite V3 Graph"""
    
    # 1. 记录请求，方便调试 422 或参数问题
    logger.info(f"🚀 [API] 收到请求 | 字数要求: {req.word_count} | 原始内容长度: {len(req.content)}")
    
    # 创建新的 Project ID
    project_id = str(uuid.uuid4())
    
    # 初始化状态
    initial_state: DeepWriteState = {
        "project_id": project_id,
        "topic": req.topic or "", 
        "raw_content": req.content,
        "user_instruction": req.instruction,
        "target_word_count": str(req.word_count) + "字", # 强转 string
        "fast_mode": req.fast_mode,
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
            # 数据库占位
            create_writing_project(
                title=req.topic or "未命名项目", 
                requirements=req.instruction,
                source_type="newsroom_v3",
                source_data=req.content[:5000]
            )
            
            accumulated_drafts = [] 
            
            # 执行 Graph
            async for event in write_graph_v3.astream(initial_state, config={"recursion_limit": 100}):
                for node_name, update in event.items():
                    logs = update.get("run_logs", [])
                    
                    # 实时草稿拼接逻辑
                    if "section_drafts" in update and update["section_drafts"]:
                        new_sections = update["section_drafts"]
                        accumulated_drafts.extend(new_sections)
                    
                    # 优先显示 final_article，其次显示草稿拼接
                    current_display_text = update.get("final_article", "")
                    if not current_display_text:
                        current_display_text = "\n\n".join(accumulated_drafts)
                    
                    current_topic = update.get("topic", "")

                    payload = {
                        "node": node_name,
                        "logs": logs,
                        "generated_topic": current_topic,
                        "display_content": current_display_text,
                        "is_final": bool(update.get("final_article"))
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
            logger.info(f"✅ [API] 任务结束 ProjectID: {project_id}")
            
        except Exception as e:
            logger.error(f"❌ [API] 任务异常: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")