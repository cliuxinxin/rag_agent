"""
深度写作相关 API 路由（基于 write_graph_v2）
提供一键深度写作能力：根据用户需求与可选素材生成结构化长文。
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import uuid
import json
import asyncio
import tempfile
import os

from src.state import NewsroomState
from src.graphs.write_graph_v2 import planning_graph, drafting_graph
from src.nodes.write_nodes_v2 import outline_architect_node, outline_refiner_node
from src.nodes.common import get_llm
from langchain_core.messages import HumanMessage
from langchain_community.document_loaders import PyPDFLoader
from src.logger import get_logger
from src.db import (
    create_writing_project, 
    get_writing_project, 
    update_project_outline, 
    update_project_draft,
    get_all_projects,
    delete_project
)

logger = get_logger("WriteAPI")

router = APIRouter()


class PlanRequest(BaseModel):
    """策划请求体"""
    topic: str
    article_type: str = "tech"
    word_count: int = 2000
    source_text: Optional[str] = ""
    style_tone: str = "标准风格"
    article_length: str = "标准篇幅"
    must_haves: str = ""
    enable_web_search: bool = False
    auto_mode: bool = False

class OutlineRequest(BaseModel):
    """生成大纲请求体"""
    project_id: str
    selected_angle: Dict

class RefineOutlineRequest(BaseModel):
    """修改大纲请求体"""
    project_id: str
    feedback: str

class DraftRequest(BaseModel):
    """生成正文请求体"""
    project_id: str

class TwitterRequest(BaseModel):
    """生成推特文案请求体"""
    article_content: str
    mode: str  # "thread" or "long"

class WriteResponse(BaseModel):
    project_id: str
    angles: Optional[List[Dict]] = None
    outline: Optional[List[Dict]] = None
    full_draft: Optional[str] = None
    final_article: Optional[str] = None
    critique_notes: Optional[str] = None

def _get_initial_state(req: PlanRequest, project_id: str) -> NewsroomState:
    user_requirement = (
        f"主题：{req.topic}\n"
        f"类型：{req.article_type}\n"
        f"字数：约 {req.word_count} 字\n"
        f"必须包含：{req.must_haves or '无特别要求'}"
    )
    return {
        "project_id": project_id,
        "enable_web_search": req.enable_web_search,
        "full_content": req.source_text or req.topic,
        "user_requirement": user_requirement,
        "style_tone": req.style_tone,
        "article_length": req.article_length,
        "must_haves": req.must_haves,
        "generated_angles": [],
        "selected_angle": {},
        "outline": [],
        "user_feedback_on_outline": "",
        "current_section_index": 0,
        "section_drafts": [],
        "research_cache": "",
        "full_draft": "",
        "critique_notes": "",
        "final_article": "",
        "loop_count": 0,
        "next": "MacroSearch",
        "macro_search_context": "",
        "run_logs": [],
    }

@router.post("/plan", response_model=WriteResponse, summary="Step 1: 运行 Planning Graph 获取角度")
async def plan_article(req: PlanRequest):
    project_id = create_writing_project(
        title=req.topic,
        requirements=json.dumps(req.dict(), ensure_ascii=False),
        source_type="text",
        source_data=req.source_text or req.topic
    )
    
    state = _get_initial_state(req, project_id)
    
    try:
        # 运行策划图
        for step in planning_graph.stream(state, config={"recursion_limit": 20}):
            for _, update in step.items():
                if isinstance(update, dict):
                    state.update(update)
        
        return WriteResponse(
            project_id=project_id,
            angles=state.get("generated_angles", [])
        )
    except Exception as e:
        logger.error(f"[WriteAPI] 策划阶段失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"策划阶段失败：{str(e)}")

@router.post("/outline", response_model=WriteResponse, summary="Step 2: 生成大纲")
async def generate_outline(req: OutlineRequest):
    project = get_writing_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    plan_req = PlanRequest(**json.loads(project['requirements']))
    state = _get_initial_state(plan_req, req.project_id)
    state["selected_angle"] = req.selected_angle
    
    try:
        # 调用大纲生成节点
        outline_result = outline_architect_node(state)
        if isinstance(outline_result, dict):
            state.update(outline_result)
        
        update_project_outline(req.project_id, state["outline"])
        
        return WriteResponse(
            project_id=req.project_id,
            outline=state["outline"]
        )
    except Exception as e:
        logger.error(f"[WriteAPI] 大纲生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"大纲生成失败：{str(e)}")

@router.post("/refine_outline", response_model=WriteResponse, summary="Step 2.5: 修改大纲")
async def refine_outline(req: RefineOutlineRequest):
    project = get_writing_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    plan_req = PlanRequest(**json.loads(project['requirements']))
    state = _get_initial_state(plan_req, req.project_id)
    state["outline"] = project["outline_data"]
    state["user_feedback_on_outline"] = req.feedback
    
    try:
        refine_result = outline_refiner_node(state)
        if isinstance(refine_result, dict):
            state.update(refine_result)
            
        update_project_outline(req.project_id, state["outline"])
        
        return WriteResponse(
            project_id=req.project_id,
            outline=state["outline"]
        )
    except Exception as e:
        logger.error(f"[WriteAPI] 大纲修改失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"大纲修改失败：{str(e)}")

@router.post("/draft", summary="Step 3: 流式生成正文")
async def generate_draft(req: DraftRequest):
    project = get_writing_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    plan_req = PlanRequest(**json.loads(project['requirements']))
    state = _get_initial_state(plan_req, req.project_id)
    state["outline"] = project["outline_data"]
    
    async def event_generator():
        try:
            # 运行写作流水线
            for step in drafting_graph.stream(state, config={"recursion_limit": 100}):
                for node_name, update in step.items():
                    if isinstance(update, dict):
                        state.update(update)
                        # 发送当前节点、日志和审阅意见
                        payload = {
                            'node': node_name, 
                            'logs': update.get('run_logs', []),
                            'critique_notes': state.get('critique_notes', '')
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            
            # 最后发送完整结果
            update_project_draft(req.project_id, state.get("final_article", state.get("full_draft", "")))
            final_data = {
                "project_id": req.project_id,
                "full_draft": state.get("full_draft", ""),
                "final_article": state.get("final_article", ""),
                "critique_notes": state.get("critique_notes", "")
            }
            yield f"data: {json.dumps({'node': 'FINISH', 'result': final_data}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[WriteAPI] 写作流式生成失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'node': 'ERROR', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/extract_text", summary="从文件提取文本")
async def extract_text(file: UploadFile = File(...)):
    """从 PDF 或 TXT 文件提取纯文本内容"""
    if not (file.filename.endswith('.pdf') or file.filename.endswith('.txt')):
        raise HTTPException(status_code=400, detail="只支持 PDF 或 TXT 文件")
    
    content = await file.read()
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        full_text = ""
        if file_ext == ".pdf":
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            full_text = "\n\n".join([p.page_content for p in pages])
        else:
            full_text = content.decode("utf-8")
        
        return {"text": full_text}
    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        raise HTTPException(status_code=500, detail=f"文本提取失败: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.post("/generate_twitter", summary="生成推特文案")
async def generate_twitter(req: TwitterRequest):
    """将文章内容转化为推特格式"""
    try:
        llm = get_llm()
        
        if req.mode == "thread":
            prompt = f"""
            你是一个拥有百万粉丝的 X (Twitter) 科技大V。请将下文转化为适合 X 发布的 Thread（连推）。
            
            【🚨 致命字数限制（极度重要）】：
            X 平台限制每条推文 280 字符（中文字符和 Emoji 各占 2 字符）。
            因此，**每条推文的绝对上限是 130 个中文字符**！
            你必须在这个极限框框内跳舞，绝对不能超字数，否则无法发布！
            
            【内容与排版要求】：
            1. 黄金首推（1/N）：极具吸引力的 Hook，一句话点破痛点或抛出反常识结论。
            2. 极高信息密度：在 130 字以内，每一推必须是一条完整的逻辑、一个震撼的数据或一句金句。删掉所有过渡性的废话。
            3. 🚫 严禁使用 Markdown：绝对不要出现 `**加粗**`、`# 标题`、`- 列表` 等符号，X 平台不支持！
            4. 🎨 视觉锚点：由于不能加粗，请在每推开头或关键数据前使用 1-2 个 Emoji（如 💡, 📊, ⚠️, 📌）作为视觉焦点。
            5. 【排版工具指令】：为了让排版工具自动识别，每条推文之间，必须且只能使用连续的四个换行符（即空三行）隔开！
            
            【原文】：
            {req.article_content}
            """
        else:
            prompt = f"""
            你是一个拥有百万粉丝 of X (Twitter) 科技大V。请将下文转化为一篇【超长推文 (Long Tweet)】。
            
            【长推文排版要求】：
            1. 蓝V不受字数限制，请勿切分成多条帖子，必须输出一篇完整的长文。
            2. 🚫 严禁使用 Markdown：绝对不要出现 `**加粗**`、`# 标题` 等符号！
            3. 🎨 巧用 Emoji 划分结构：用 Emoji（如 🔹, 💡, 🚀, 📌 等）来替代 Markdown 的强调效果。
            4. 结构紧凑：第一段必须是极具吸引力的 Hook。
            5. 提炼干货：提取原文最核心的金句和数据。
            6. 结尾加上互动引导。
            
            【原文】：
            {req.article_content}
            """
            
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        thread_result = response.content
        # 清洗 Markdown
        thread_result = thread_result.replace("**", "").replace("__", "").replace("### ", "").replace("## ", "").replace("# ", "")
        
        return {"content": thread_result}
    except Exception as e:
        logger.error(f"Twitter generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"推特文案生成失败: {str(e)}")

@router.get("/projects", summary="获取所有写作项目")
async def list_projects():
    try:
        projects = get_all_projects()
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目列表失败：{str(e)}")

@router.get("/projects/{project_id}", summary="获取写作项目详情")
async def get_project_detail(project_id: str):
    project = get_writing_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project

@router.delete("/projects/{project_id}", summary="删除写作项目")
async def remove_project(project_id: str):
    try:
        delete_project(project_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除项目失败：{str(e)}")

