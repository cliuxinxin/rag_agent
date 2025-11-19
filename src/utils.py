"""文档加载与切分工具函数。"""

import tempfile
import os
import json
from typing import List
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def load_file(uploaded_file) -> List[Document]:
    """将 Streamlit 上传的文件转换为 Document 对象列表。"""
    file_ext = uploaded_file.name.split(".")[-1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        if file_ext == "pdf":
            loader = PyPDFLoader(tmp_path)
        else:
            loader = TextLoader(tmp_path, encoding="utf-8")
        return loader.load()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def split_documents(docs: List[Document], chunk_size: int = 500) -> List[Document]:
    """切分文档。"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "！", "？", "；", "；", " ", ""]
    )
    return text_splitter.split_documents(docs)


def serialize_document(doc: Document) -> dict:
    """将 Document 对象序列化为字典。"""
    return {
        "page_content": doc.page_content,
        "metadata": doc.metadata
    }


def deserialize_document(data: dict) -> Document:
    """从字典反序列化为 Document 对象。"""
    return Document(
        page_content=data["page_content"],
        metadata=data["metadata"]
    )


def serialize_documents(docs: List[Document]) -> List[dict]:
    """将 Document 对象列表序列化为字典列表。"""
    return [serialize_document(doc) for doc in docs]


def deserialize_documents(data: List[dict]) -> List[Document]:
    """从字典列表反序列化为 Document 对象列表。"""
    return [deserialize_document(item) for item in data]