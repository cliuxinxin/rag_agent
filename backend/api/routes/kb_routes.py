"""
知识库管理相关 API 路由
提供知识库列表、删除、文件上传并向量化等功能
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
import tempfile
import os

from langchain_core.documents import Document
from pypdf import PdfReader

from src.storage import (
    list_kbs,
    delete_kb,
    save_kb,
    get_kb_details,
    get_kb_documents,
    search_kb_chunks,
    resume_kb_embedding,
    get_chunk_vector
)
from src.utils import split_documents

router = APIRouter()

@router.post("/{kb_name}/resume", summary="断点续传/修复知识库索引")
async def resume_kb(kb_name: str):
    """
    当健康度检查发现 mismatch 或 corrupted 时，调用此接口触发断点续传或修复。
    """
    try:
        current, total = resume_kb_embedding(kb_name)
        return {"status": "success", "current": current, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复知识库失败：{str(e)}")

@router.get("/{kb_name}/chunks/{chunk_index}/vector", summary="获取特定片段的向量数值")
async def get_vector(kb_name: str, chunk_index: int):
    """
    调试接口：获取 FAISS 索引中特定 ID 的向量原始数值。
    """
    res = get_chunk_vector(kb_name, chunk_index)
    if not res["exists"]:
        raise HTTPException(status_code=404, detail=res["msg"])
    return res


@router.get("/list", summary="获取知识库列表")
async def get_kb_list():
    """
    获取当前所有知识库名称列表
    """
    return {"kbs": list_kbs()}


@router.get("/health", summary="获取所有知识库的健康状态")
async def get_all_kb_health():
    """
    返回所有知识库的健康度信息，用于前端总览面板。
    """
    kbs = list_kbs()
    details = [get_kb_details(name) for name in kbs]
    return {"items": details}


@router.delete("/{kb_name}", summary="删除知识库")
async def delete_knowledge_base(kb_name: str):
    """
    删除指定知识库（JSON 与向量索引）
    """
    try:
        delete_kb(kb_name)
        return {"status": "deleted", "name": kb_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除知识库失败：{str(e)}")


@router.post("/add_text", summary="添加纯文本到知识库")
async def add_text_to_kb(
    kb_name: str = Form(...),
    text: str = Form(...),
    doc_name: str = Form("粘贴的文本"),
    mode: str = Form("append")
):
    """
    将直接粘贴的纯文本切分后写入指定知识库并向量化。
    """
    if mode not in ("append", "new"):
        raise HTTPException(status_code=400, detail="mode 必须是 'append' 或 'new'")

    if mode == "new":
        try:
            delete_kb(kb_name)
        except Exception:
            pass

    if not text.strip():
        raise HTTPException(status_code=400, detail="文本内容为空")

    try:
        raw_doc = Document(
            page_content=text,
            metadata={"source": doc_name}
        )
        
        # 文本切分
        from src.utils import split_documents
        chunks = split_documents([raw_doc])

        # 写入并向量化
        save_kb(kb_name, chunks)

        return {"status": "success", "chunks_count": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'添加文本失败：{str(e)}')


@router.post("/upload", summary="上传文件并写入知识库")
async def upload_to_kb(
    kb_name: str = Form(...),
    files: List[UploadFile] = File(...),
    mode: str = Form("append"),  # append 或 new
):
    """
    上传一个或多个文件，切分后写入指定知识库并向量化。

    - kb_name: 知识库名称
    - files: 上传文件列表（支持 PDF、TXT 等）
    - mode: "append" 追加 / "new" 重建
    """
    if mode not in ("append", "new"):
        raise HTTPException(status_code=400, detail="mode 必须是 'append' 或 'new'")

    # 如果是重建模式，先删除旧知识库
    if mode == "new":
        try:
            delete_kb(kb_name)
        except Exception:
            # 不存在时忽略错误
            pass

    raw_docs: List[Document] = []

    try:
        for file in files:
            suffix = os.path.splitext(file.filename)[1].lower() or ".txt"

            # 将 UploadFile 写入临时文件，供 LangChain loader 使用
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # 直接使用 pypdf / 文本读取，避免 langchain_community 的兼容性问题
                if suffix == ".pdf":
                    reader = PdfReader(tmp_path)
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        if not text.strip():
                            continue
                        raw_docs.append(
                            Document(
                                page_content=text,
                                metadata={"source": file.filename, "page": i},
                            )
                        )
                else:
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    if text.strip():
                        raw_docs.append(
                            Document(
                                page_content=text,
                                metadata={"source": file.filename},
                            )
                        )
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        if not raw_docs:
            return {"status": "no_content", "chunks_count": 0}

        # 文本切分
        from src.utils import split_documents
        chunks = split_documents(raw_docs)

        # 写入并向量化
        save_kb(kb_name, chunks)

        return {"status": "success", "chunks_count": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'上传知识库失败：{str(e)}')


@router.get("/{kb_name}/documents", summary="获取知识库的文档列表视图")
async def get_kb_documents_view(kb_name: str):
    """
    以“文档”为粒度返回知识库内容，便于前端展示。
    """
    try:
        docs = get_kb_documents(kb_name)
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识库文档失败：{str(e)}")


@router.get("/{kb_name}/health", summary="获取单个知识库的健康状态")
async def get_single_kb_health(kb_name: str):
    """
    返回单个知识库的健康度信息。
    """
    try:
        info = get_kb_details(kb_name)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识库健康度失败：{str(e)}")


@router.get("/{kb_name}/chunks/search", summary="在知识库中搜索片段")
async def search_kb(
    kb_name: str,
    q: str,
    limit: int = 20,
):
    """
    在知识库的 JSON 片段中进行关键词搜索，用于调试向量库。
    """
    if not q:
        raise HTTPException(status_code=400, detail="缺少搜索关键词 q")

    try:
        results = search_kb_chunks(kb_name, q, limit=limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败：{str(e)}")

