"""
DeepWrite V3 (新闻工作室) API 路由
支持两阶段流程：
  1. init_proposal: 生成角度 -> 返回 3 个选项
  2. run_generation: 用户选择 + 生成全文
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Union, List, Dict
import json
import uuid
from datetime import datetime

from src.graphs.write_graph_v3 import write_graph_v3
from src.state import DeepWriteState
from src.logger import get_logger
from src.db import (
    create_writing_project, 
    get_writing_project, 
    update_project_process_data,
    get_projects_by_source
)
from src.nodes.write_nodes_v3 import (
    angle_proposer_node,
    structure_gen_node,
    writer_node,
    reviewer_node,
    polisher_node,
    fast_finish_node
)

logger = get_logger("API_WriteV3")
router = APIRouter(tags=["write-v3"])

# === Pydantic Models ===

class InitProposalRequest(BaseModel):
    """启动请求：素材 -> 获取角度选项"""
    content: str
    instruction: str = "风格专业，逻辑清晰"

class RunGenerationRequest(BaseModel):
    """执行请求：选择角度 -> 生成全文"""
    project_id: str
    selected_angle: Dict  # 完整的 angle 对象
    word_count: Union[str, int] = "1500"
    fast_mode: bool = False

# === 兼容旧版本的写法 ===
class WriteRequest(BaseModel):
    content: str = Field(..., description="原始素材")
    topic: Optional[str] = Field(default="", description="主题")
    instruction: str = Field(default="风格专业，逻辑清晰", description="要求")
    fast_mode: bool = Field(default=False, description="极速模式")
    word_count: Union[str, int] = Field(default="1500", description="字数")

# === API Endpoints ===

@router.post("/init_proposal")
async def init_proposal(req: InitProposalRequest):
    """
    第一步：分析素材，生成 3 个切入角度供用户选择
    
    返回 Server-Sent Events 流：
    - type: "angles" -> 返回角度选项和 project_id
    - [DONE] -> 结束
    """
    project_id = str(uuid.uuid4())
    logger.info(f"[{project_id}] 启动新项目：init_proposal")
    
    # 创建 DB 记录
    try:
        create_writing_project(
            project_id=project_id,
            title="新闻策划（筹备中）",
            requirements=req.instruction,
            source_type="newsroom_v3",
            source_data=req.content
        )
        logger.info(f"[{project_id}] 项目已创建")
    except Exception as e:
        logger.error(f"[{project_id}] 创建项目失败: {e}")
        raise HTTPException(500, f"创建项目失败: {e}")
    
    initial_state = {
        "project_id": project_id,
        "raw_content": req.content,
        "user_instruction": req.instruction,
        "topic": "",
        "topic_analysis": "",
        "outline": [],
        "current_section_index": 0,
        "section_drafts": [],
        "critique_notes": "",
        "final_article": "",
        "target_word_count": "1500",
        "fast_mode": False,
        "angles_options": [],
        "selected_angle_data": {},
        "run_logs": []
    }
    
    async def event_generator():
        try:
            # 仅运行 AngleProposer 节点
            logger.info(f"[{project_id}] 开始运行 AngleProposer 节点")
            update = await angle_proposer_node(initial_state)
            
            angles = update.get("angles_options", [])
            logs = update.get("run_logs", [])
            
            # 返回角度选项
            for log in logs:
                yield f"data: {json.dumps({'type': 'log', 'message': log}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'type': 'angles', 'data': angles, 'pid': project_id}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            
            logger.info(f"[{project_id}] AngleProposer 完成，生成 {len(angles)} 个方向")
            
        except Exception as e:
            logger.error(f"[{project_id}] AngleProposer 执行失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/run_generation")
async def run_generation(req: RunGenerationRequest):
    """
    第二步：用户选择角度后，生成标题、大纲和全文
    
    返回 Server-Sent Events 流：
    - node: 节点名 (StructureGen, Writer, Reviewer, Polisher 等)
    - logs: 该节点的日志数组
    - topic: 生成的标题（仅 StructureGen）
    - display_content: 实时显示的文章内容
    - is_final: 是否是最终成稿
    """
    project_id = req.project_id
    logger.info(f"[{project_id}] 启动生成流程，选定方向: {req.selected_angle.get('id')}")
    
    # 从 DB 恢复项目信息
    project = get_writing_project(project_id)
    if not project:
        logger.error(f"[{project_id}] 项目未找到")
        raise HTTPException(404, f"项目不存在: {project_id}")
    
    # 更新选择到 DB
    try:
        update_project_process_data(project_id, {"selected_angle": req.selected_angle})
    except Exception as e:
        logger.warning(f"过程数据保存失败: {e}")
    
    # 构造初始状态
    state = {
        "project_id": project_id,
        "raw_content": project.get("source_data", ""),
        "user_instruction": project.get("requirements", ""),
        "selected_angle_data": req.selected_angle,
        "target_word_count": req.word_count,
        "fast_mode": req.fast_mode,
        "topic": "",
        "topic_analysis": "",
        "outline": [],
        "current_section_index": 0,
        "section_drafts": [],
        "critique_notes": "",
        "final_article": "",
        "angles_options": [],
        "run_logs": []
    }
    
    async def event_generator():
        try:
            # 1. 生成结构（标题 + 大纲）
            logger.info(f"[{project_id}] 阶段 1: StructureGen")
            structure_update = await structure_gen_node(state)
            state.update(structure_update)
            
            for log in structure_update.get("run_logs", []):
                yield f"data: {json.dumps({'node': 'StructureGen', 'log': log}, ensure_ascii=False)}\n\n"
            
            topic = structure_update.get("topic", "")
            yield f"data: {json.dumps({'type': 'title', 'topic': topic, 'node': 'StructureGen'}, ensure_ascii=False)}\n\n"
            
            # 2. 循环写作
            logger.info(f"[{project_id}] 阶段 2: 开始写作循环")
            outline = state.get("outline", [])
            
            while state["current_section_index"] < len(outline):
                w_update = await writer_node(state)
                if not w_update:
                    break
                
                state.update(w_update)
                
                # 返回实时草稿
                for log in w_update.get("run_logs", []):
                    yield f"data: {json.dumps({'node': 'Writer', 'log': log}, ensure_ascii=False)}\n\n"
                
                # 返回当前累积的内容
                draft_text = "\n\n".join(state.get("section_drafts", []))
                yield f"data: {json.dumps({'type': 'content', 'node': 'Writer', 'content': draft_text}, ensure_ascii=False)}\n\n"
            
            logger.info(f"[{project_id}] 所有章节写完")
            
            # 3. 收尾逻辑
            if req.fast_mode:
                logger.info(f"[{project_id}] 极速模式：跳过审阅")
                f_update = await fast_finish_node(state)
                state.update(f_update)
                
                for log in f_update.get("run_logs", []):
                    yield f"data: {json.dumps({'node': 'FastFinish', 'log': log}, ensure_ascii=False)}\n\n"
                
                yield f"data: {json.dumps({'type': 'final', 'node': 'FastFinish', 'content': state['final_article']}, ensure_ascii=False)}\n\n"
            else:
                logger.info(f"[{project_id}] 启动审阅阶段")
                r_update = await reviewer_node(state)
                state.update(r_update)
                
                for log in r_update.get("run_logs", []):
                    yield f"data: {json.dumps({'node': 'Reviewer', 'log': log}, ensure_ascii=False)}\n\n"
                
                logger.info(f"[{project_id}] 启动润色阶段")
                p_update = await polisher_node(state)
                state.update(p_update)
                
                for log in p_update.get("run_logs", []):
                    yield f"data: {json.dumps({'node': 'Polisher', 'log': log}, ensure_ascii=False)}\n\n"
                
                yield f"data: {json.dumps({'type': 'final', 'node': 'Polisher', 'content': state['final_article']}, ensure_ascii=False)}\n\n"
            
            logger.info(f"[{project_id}] 全流程完成")
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"[{project_id}] 生成过程出错: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/logs/{project_id}")
async def get_project_logs(project_id: str):
    """
    获取项目的详细 LLM 交互日志
    """
    project = get_writing_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")
    
    logs = project.get("logs", [])
    return {"logs": logs, "project_id": project_id}


@router.get("/projects")
async def list_projects():
    """
    获取所有 newsroom_v3 类型的项目
    """
    try:
        projects = get_projects_by_source("newsroom_v3")
        return {
            "count": len(projects),
            "projects": projects
        }
    except Exception as e:
        logger.error(f"获取项目列表失败: {e}")
        raise HTTPException(500, f"获取项目列表失败: {e}")


@router.get("/project/{project_id}")
async def get_project_detail(project_id: str):
    """
    获取项目的完整详情
    """
    project = get_writing_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")
    
    return {
        "id": project["id"],
        "title": project.get("title", "未命名"),
        "status": project.get("status", "draft"),
        "created_at": project.get("created_at", ""),
        "updated_at": project.get("updated_at", ""),
        "requirements": project.get("requirements", ""),
        "source_type": project.get("source_type", ""),
        "full_draft": project.get("full_draft", ""),
        "outline": project.get("outline_data", []),
        "logs": project.get("logs", []),
        "process_data": project.get("process_data", {})
    }

# === 兼容旧版 /run 端点 ===
@router.post("/run")
async def run_write_v3(req: WriteRequest):
    """流式运行 DeepWrite V3 Graph (旧版本兼容)"""
    
    logger.info(f"🚀 [API] 收到请求 | 字数要求: {req.word_count} | 原始内容长度: {len(req.content)}")
    
    project_id = str(uuid.uuid4())
    
    # 创建项目
    try:
        create_writing_project(
            project_id=project_id,
            title=req.topic or "未命名项目", 
            requirements=req.instruction,
            source_type="newsroom_v3",
            source_data=req.content
        )
    except Exception as e:
        logger.error(f"创建项目失败: {e}")
    
    initial_state: DeepWriteState = {
        "project_id": project_id,
        "topic": req.topic or "", 
        "raw_content": req.content,
        "user_instruction": req.instruction,
        "target_word_count": str(req.word_count),
        "fast_mode": req.fast_mode,
        "topic_analysis": "",
        "outline": [],
        "current_section_index": 0,
        "section_drafts": [],
        "critique_notes": "",
        "final_article": "",
        "angles_options": [],
        "selected_angle_data": {},
        "run_logs": []
    }
    
    async def event_generator():
        try:
            accumulated_drafts = [] 
            
            # 执行 Graph
            async for event in write_graph_v3.astream(initial_state, config={"recursion_limit": 100}):
                for node_name, update in event.items():
                    logs = update.get("run_logs", [])
                    
                    if "section_drafts" in update and update["section_drafts"]:
                        new_sections = update["section_drafts"]
                        accumulated_drafts.extend(new_sections)
                    
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