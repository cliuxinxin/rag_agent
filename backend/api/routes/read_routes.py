"""
深度阅读相关 API 路由
提供 PDF 上传、文档分析、报告生成等功能
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import tempfile
import os
import sys
import json
from typing import AsyncGenerator, List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from src.graphs.deep_read_graph import deep_read_graph
from src.state import AgentState
from src.db import save_report, get_all_reports, get_report_content, delete_report
from src.logger import get_logger

logger = get_logger("ReadAPI")

router = APIRouter()

@router.get("/reports", summary="获取历史报告列表")
async def list_reports():
    """获取所有已生成的深度解读报告"""
    try:
        reports = get_all_reports()
        return {"reports": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取报告列表失败：{str(e)}")

@router.get("/reports/{report_id}", summary="获取报告详情")
async def get_report(report_id: str):
    """根据 ID 获取报告完整内容"""
    report = get_report_content(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report

@router.delete("/reports/{report_id}", summary="删除报告")
async def remove_report(report_id: str):
    """删除指定的报告"""
    try:
        delete_report(report_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除报告失败：{str(e)}")

@router.post("/upload", summary="上传 PDF 文件")
async def upload_pdf(file: UploadFile = File(...)):
    """
    上传 PDF 文件用于深度阅读分析
    
    **请求体:** FormData
    - `file`: PDF 文件
    
    **返回:** 临时文件路径和文件信息
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    
    # 读取文件内容
    content = await file.read()
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    return {
        "filename": file.filename,
        "temp_path": tmp_path,
        "size": len(content),
        "status": "uploaded"
    }


@router.post("/analyze", summary="分析文档（流式）")
async def analyze_document(
    file_path: str = Form(...),
    query: str = Form("请深入分析这份文档，并生成结构化报告。"),
    doc_title: str = Form("未命名文档")
):
    """
    使用 deep_read_graph 对上传的 PDF 文档进行深度分析，并通过 SSE 流式返回进度与结果。

    **请求体:** FormData
    - `file_path`: 临时文件路径（由 /upload 返回）
    - `query`: 用户问题或分析指令（目前主要用于日志，可扩展）
    - `doc_title`: 文档标题，用于报告抬头

    **返回:** SSE 流，包含分析进度和最终报告
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 读取全文内容（目前按纯文本读取，后续可以接入更复杂的 loader）
    try:
        from langchain_community.document_loaders import PyPDFLoader, TextLoader
        full_text = ""

        if file_path.lower().endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            full_text = "\n\n".join([p.page_content for p in pages])
        else:
            # 回退：按 UTF-8 文本读取
            with open(file_path, "r", encoding="utf-8") as f:
                full_text = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'读取文件失败：{str(e)}')

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空，无法分析")

    # 构造 deep_read_graph 所需的初始状态
    initial_state: AgentState = {
        "messages": [],
        "full_content": full_text,
        "doc_title": doc_title,
        "user_goal": query,
        "next": "Planner",
        "loop_count": 0,
        "current_question": "",
        "qa_pairs": [],
        "final_report": "",
        "suggested_questions": [],
        "source_documents": [],
        "vector_store": None,
        "current_search_query": "",
        "final_evidence": [],
        "attempted_searches": [],
        "failed_topics": [],
        "research_notes": [],
        "kb_summary": "",
        "kb_names": [],
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        """
        将 deep_read_graph.stream 的执行过程包装为 SSE 流。
        """
        try:
            # 开始信号
            yield f"data: {json.dumps({'type': 'progress', 'message': '开始分析文档...', 'node': 'system'}, ensure_ascii=False)}\n\n"

            for step in deep_read_graph.stream(initial_state, config={"recursion_limit": 50}):
                for node_name, update in step.items():
                    payload: dict = {"type": "progress", "node": node_name}

                    # LangGraph 返回的 update 可能是 AgentState 的子集（dict）
                    if isinstance(update, dict):
                        # Planner：报告当前问题
                        if node_name == "Planner":
                            msg = update.get("current_question") or "规划下一步分析任务..."
                            payload["message"] = msg

                        # Researcher：返回最新 QA
                        elif node_name == "Researcher":
                            qa_pairs = update.get("qa_pairs") or []
                            payload["message"] = f"已完成 {len(qa_pairs)} 轮查证"
                            if qa_pairs:
                                payload["latest_qa"] = qa_pairs[-1]

                        # Writer：报告生成中间稿
                        elif node_name == "Writer":
                            report = update.get("final_report", "")
                            payload["message"] = "正在撰写主体报告..."
                            # 为了避免多次覆盖，前端可以选择只在最后展示
                            if report:
                                payload["report_preview"] = report[:1000]

                        # Outlooker：最终报告
                        elif node_name == "Outlooker":
                            final_report = update.get("final_report", "")
                            payload["message"] = "分析完成，生成扩展思考与总结。"
                            payload["final_report"] = final_report
                            # 保存到数据库
                            if final_report:
                                try:
                                    save_report(doc_title, doc_title, final_report)
                                except Exception as db_err:
                                    logger.error(f"Failed to save report to DB: {db_err}")

                        else:
                            payload["message"] = f"{node_name} 节点已完成一步处理。"

                    else:
                        # 非 dict 的 update，直接转字符串
                        payload["message"] = str(update)

                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 结束信号
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_payload = {
                "type": "error",
                "message": str(e),
                "node": "system",
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/analyze_text", summary="分析纯文本（流式）")
async def analyze_text(
    text: str = Form(...),
    doc_title: str = Form("粘贴的文本")
):
    """
    对直接粘贴的纯文本进行深度分析，并通过 SSE 流式返回进度与结果。
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本内容为空，无法分析")

    # 构造 deep_read_graph 所需的初始状态
    initial_state: AgentState = {
        "messages": [],
        "full_content": text,
        "doc_title": doc_title,
        "user_goal": "请深入分析这份文本，并生成结构化报告。",
        "next": "Planner",
        "loop_count": 0,
        "current_question": "",
        "qa_pairs": [],
        "final_report": "",
        "suggested_questions": [],
        "source_documents": [],
        "vector_store": None,
        "current_search_query": "",
        "final_evidence": [],
        "attempted_searches": [],
        "failed_topics": [],
        "research_notes": [],
        "kb_summary": "",
        "kb_names": [],
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': '开始分析文本...', 'node': 'system'}, ensure_ascii=False)}\n\n"

            for step in deep_read_graph.stream(initial_state, config={"recursion_limit": 50}):
                for node_name, update in step.items():
                    payload: dict = {"type": "progress", "node": node_name}
                    if isinstance(update, dict):
                        if node_name == "Planner":
                            payload["message"] = update.get("current_question") or "规划下一步分析任务..."
                        elif node_name == "Researcher":
                            qa_pairs = update.get("qa_pairs") or []
                            payload["message"] = f"已完成 {len(qa_pairs)} 轮查证"
                            if qa_pairs: payload["latest_qa"] = qa_pairs[-1]
                        elif node_name == "Writer":
                            payload["message"] = "正在撰写主体报告..."
                            if update.get("final_report"): payload["report_preview"] = update["final_report"][:1000]
                        elif node_name == "Outlooker":
                            final_report = update.get("final_report", "")
                            payload["message"] = "分析完成。"
                            payload["final_report"] = final_report
                            if final_report: save_report(doc_title, doc_title, final_report)
                        else:
                            payload["message"] = f"{node_name} 节点已完成。"
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/temp/{filename}", summary="下载临时文件")
async def download_temp_file(filename: str):
    """
    下载临时存储的文件
    
    **路径参数:**
    - `filename`: 文件名
    
    **返回:** 文件二进制流
    """
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    from fastapi.responses import FileResponse
    return FileResponse(file_path)
