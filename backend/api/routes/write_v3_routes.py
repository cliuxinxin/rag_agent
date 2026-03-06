"""
DeepWrite V3 (Newsroom Studio) API 路由
提供原子化能力 API，由前端按需调用
"""
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import uuid

from src.db import (
    create_writing_project, 
    get_writing_project, 
    update_project_assets, 
    update_project_section_content
)
from src.nodes.common import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from src.prompts_v3 import (
    get_v3_system_prompt, 
    get_outline_gen_prompt, 
    get_section_write_prompt, 
    get_polishing_prompt
)
from src.logger import get_logger

logger = get_logger("WriteV3API")
router = APIRouter()

# === Models ===
class CreateProjectReq(BaseModel):
    title: str

class UpdateAssetsReq(BaseModel):
    project_id: str
    assets: List[Dict]  # [{"id": "...", "type": "text", "content": "..."}]

class GenerateOutlineReq(BaseModel):
    project_id: str
    requirements: str
    tone: str
    length: str

class GenerateSectionReq(BaseModel):
    project_id: str
    section_id: str  # UUID within the outline
    tone: str
    length: str

class PolishSectionReq(BaseModel):
    content: str
    instruction: str

class SaveProjectStateReq(BaseModel):
    project_id: str
    outline_data: List[Dict]


# === Helpers ===
def _build_assets_text(assets: List[Dict]) -> str:
    text = ""
    for idx, a in enumerate(assets):
        text += f"\n--- 素材 {idx+1} ({a.get('type')}) ---\n{a.get('content')}\n"
    return text


# === Endpoints ===

@router.post("/create", summary="创建 V3 项目")
async def create_v3_project(req: CreateProjectReq):
    pid = create_writing_project(
        title=req.title, 
        requirements="", 
        source_type="newsroom_v3", 
        source_data=""
    )
    # 初始化空结构
    update_project_assets(pid, [])
    update_project_section_content(pid, [])
    return {"project_id": pid}


@router.post("/assets/update", summary="更新项目素材库")
async def update_assets(req: UpdateAssetsReq):
    update_project_assets(req.project_id, req.assets)
    return {"status": "ok"}


@router.post("/outline/generate", summary="生成大纲")
async def generate_outline(req: GenerateOutlineReq):
    project = get_writing_project(req.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    assets = json.loads(project.get("assets_data") or "[]")
    if not assets:
        raise HTTPException(400, "请先添加素材")
    
    llm = get_llm()
    sys_prompt = get_v3_system_prompt(_build_assets_text(assets), req.tone, req.length)
    user_prompt = get_outline_gen_prompt(req.requirements)
    
    try:
        res = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
        clean_json = res.content.replace("```json", "").replace("```", "").strip()
        outline_list = json.loads(clean_json)
        
        # 为每个章节分配 ID 和初始状态
        enhanced_outline = []
        for item in outline_list:
            enhanced_outline.append({
                "id": str(uuid.uuid4())[:8],
                "title": item["title"],
                "gist": item["gist"],
                "content": "",
                "status": "empty"  # empty, generating, done
            })
            
        update_project_section_content(req.project_id, enhanced_outline)
        return {"outline": enhanced_outline}
    except Exception as e:
        logger.error(f"[WriteV3] 生成大纲失败: {e}", exc_info=True)
        raise HTTPException(500, f"生成失败: {str(e)}")


@router.post("/section/stream", summary="流式生成单章内容")
async def stream_section(req: GenerateSectionReq):
    project = get_writing_project(req.project_id)
    if not project:
        raise HTTPException(404)
    
    assets = json.loads(project.get("assets_data") or "[]")
    outline = json.loads(project.get("outline_data") or "[]")
    
    # 找到目标章节和前文
    target_sec = None
    prev_context = ""
    for sec in outline:
        if sec["id"] == req.section_id:
            target_sec = sec
            break
        # 累积前文摘要，用于衔接
        if sec.get("content"):
            prev_context += f"\n[已写完章节: {sec['title']}]\n{sec['content'][-200:]}...\n"
    
    if not target_sec:
        raise HTTPException(404, "Section not found")
    
    llm = get_llm()
    sys_prompt = get_v3_system_prompt(_build_assets_text(assets), req.tone, req.length)
    user_prompt = get_section_write_prompt(target_sec['title'], target_sec['gist'], prev_context)
    
    async def generator():
        full_content = ""
        try:
            async for chunk in llm.astream([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]):
                if chunk.content:
                    full_content += chunk.content
                    yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"
            
            # 生成结束，更新数据库
            target_sec["content"] = full_content
            target_sec["status"] = "done"
            update_project_section_content(req.project_id, outline)
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"[WriteV3] 章节生成失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/project/save", summary="手动保存项目状态")
async def save_project_state(req: SaveProjectStateReq):
    """前端拖拽排序或修改内容后，手动同步回数据库"""
    update_project_section_content(req.project_id, req.outline_data)
    return {"status": "saved"}


@router.post("/polish", summary="局部润色")
async def polish_text(req: PolishSectionReq):
    llm = get_llm()
    res = llm.invoke([HumanMessage(content=get_polishing_prompt(req.content, req.instruction))])
    return {"result": res.content}