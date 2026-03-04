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

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

router = APIRouter()


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


@router.post("/analyze", summary="分析文档")
async def analyze_document(
    file_path: str = Form(...),
    query: str = Form(...)
):
    """
    分析上传的 PDF 文档并返回流式结果
    
    **请求体:** FormData
    - `file_path`: 临时文件路径
    - `query`: 用户问题或分析指令
    
    **返回:** SSE 流，包含分析进度和结果
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # TODO: 调用 deep_read_graph 的逻辑
    async def event_generator():
        try:
            # 这里应该调用原有的 deep_read_graph.stream()
            # for step in deep_read_graph.stream(initial_state):
            #     yield f"data: {json.dumps(event_data)}\n\n"
            
            # 临时实现
            yield f"data: {json.dumps({'type': 'progress', 'message': '开始分析文档...'})}\n\n"
            yield f"data: {json.dumps({'type': 'progress', 'message': '提取文本中...'})}\n\n"
            yield f"data: {json.dumps({'type': 'progress', 'message': '生成报告中...'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'result': '分析完成'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


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
