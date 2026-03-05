"""
PPT 生成相关 API 路由
提供 PPT 生成、下载等功能
"""
from fastapi import APIRouter, Response, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import json
import uuid

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.ppt_renderer import generate_ppt_binary
from src.graphs.ppt_graph import ppt_graph
from src.state import PPTState

router = APIRouter()

# 临时存储生成的 PPT 文件，供下载接口使用
PPT_CACHE = {}

class PPTRequest(BaseModel):
    topic: str
    content: str
    slide_count: int = 10

@router.post("/stream", summary="流式生成 PPT")
async def stream_ppt(req: PPTRequest):
    """
    使用 ppt_graph 流式生成 PPT，返回进度日志。
    """
    project_id = str(uuid.uuid4())
    
    initial_state: PPTState = {
        "full_content": req.content,
        "doc_title": req.topic,
        "slides_count": req.slide_count,
        "ppt_outline": [],
        "final_ppt_content": [],
        "ppt_binary": b"",
        "run_logs": []
    }

    async def event_generator():
        try:
            for step in ppt_graph.stream(initial_state, config={"recursion_limit": 20}):
                for node_name, update in step.items():
                    # 提取日志
                    logs = update.get("run_logs", [])
                    yield f"data: {json.dumps({'node': node_name, 'logs': logs}, ensure_ascii=False)}\n\n"
                    
                    if node_name == "Renderer":
                        # 渲染完成后，将二进制存入缓存
                        PPT_CACHE[project_id] = {
                            "topic": req.topic,
                            "binary": update.get("ppt_binary", b"")
                        }
            
            yield f"data: {json.dumps({'node': 'FINISH', 'project_id': project_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'node': 'ERROR', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/download/{project_id}", summary="下载生成的 PPT")
async def download_ppt(project_id: str):
    if project_id not in PPT_CACHE:
        raise HTTPException(status_code=404, detail="文件已过期或不存在")
    
    data = PPT_CACHE.pop(project_id)
    filename = f"{data['topic']}.pptx".replace(" ", "_")
    
    return Response(
        content=data['binary'],
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/template/{template_name}", summary="获取 PPT 模板")
async def get_ppt_template(template_name: str):
    """
    获取 PPT 模板文件
    
    **路径参数:**
    - `template_name`: 模板名称
    
    **返回:** PPT 模板文件二进制流
    """
    # TODO: 实现模板下载
    raise HTTPException(status_code=404, detail="模板不存在")


@router.post("/preview", summary="生成 PPT 预览")
async def generate_ppt_preview(ppt_data: PPTRequest):
    """
    生成 PPT 预览图片（Base64 编码）
    
    **请求体:** 同生成 PPT
    
    **返回:** Base64 编码的预览图片
    """
    # TODO: 实现 PPT 转图片功能
    return {
        "preview": "data:image/png;base64,...",
        "status": "preview_generated"
    }
