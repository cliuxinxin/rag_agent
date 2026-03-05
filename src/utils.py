import tempfile
import os
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from pypdf import PdfReader


def _load_from_path(path: str, filename: str) -> List[Document]:
    """
    从本地文件路径加载为 Document 列表。
    仅依赖 pypdf 与标准文本读取，避免 langchain_community 的兼容性问题。
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        reader = PdfReader(path)
        docs: List[Document] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": filename, "page": i},
                )
            )
        return docs
    else:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if not text.strip():
            return []
        return [
            Document(
                page_content=text,
                metadata={"source": filename},
            )
        ]


def load_file(uploaded_file) -> List[Document]:
    """将 Streamlit 上传的文件转换为 Document 对象列表。"""
    file_ext = uploaded_file.name.split(".")[-1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        return _load_from_path(tmp_path, uploaded_file.name)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def split_documents(docs: List[Document], chunk_size: int = 800) -> List[Document]:
    """
    【通用化修改】
    chunk_size=800: 适合承载一个完整的段落或概念。
    chunk_overlap=100: 恢复重叠，防止关键信息（如主语）刚好被切在两段之间。
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=100, 
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " ", ""]
    )
    return text_splitter.split_documents(docs)