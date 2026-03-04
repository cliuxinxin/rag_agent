"""
PPT 生成相关 API 路由
提供 PPT 生成、下载等功能
"""
from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

router = APIRouter()


class PPTOutline(BaseModel):
    """PPT 大纲数据模型"""
    topic: str
    outline: List[str]
    slide_count: Optional[int] = 10


@router.post("/generate", summary="生成 PPT")
async def generate_ppt(ppt_data: PPTOutline):
    """
    根据大纲生成 PPT
    
    **请求体:**
    ```json
    {
        "topic": "PPT 主题",
        "outline": ["第一页标题", "第二页标题", "..."],
        "slide_count": 10
    }
    ```
    
    **返回:** PPT 二进制流 (application/vnd.openxmlformats-officedocument.presentationml.presentation)
    """
    try:
        # TODO: 调用原有的 ppt_gen.py 逻辑
        # from src.ppt_renderer import generate_ppt_bytes
        # ppt_bytes = generate_ppt_bytes(ppt_data.topic, ppt_data.outline)
        
        # 临时实现 - 返回空文件
        ppt_bytes = b""
        
        filename = f"{ppt_data.topic}.pptx".replace(" ", "_").replace("/", "_")
        
        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPT 生成失败：{str(e)}")


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
async def generate_ppt_preview(ppt_data: PPTOutline):
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
