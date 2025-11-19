"""知识库持久化管理模块。"""

import os
import json
from typing import List
from pathlib import Path
from langchain_core.documents import Document

# 数据存储目录
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)


def list_kbs() -> List[str]:
    """获取所有已存在的知识库名称。"""
    return [f.stem for f in STORAGE_DIR.glob("*.json")]


def save_kb(kb_name: str, new_docs: List[Document]):
    """
    保存文档到指定知识库。
    如果是已存在的库，会追加内容。
    """
    file_path = STORAGE_DIR / f"{kb_name}.json"
    
    existing_data = []
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    
    # 将 Document 对象转换为可序列化的字典
    new_data = [
        {"page_content": doc.page_content, "metadata": doc.metadata} 
        for doc in new_docs
    ]
    
    merged_data = existing_data + new_data
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)


def load_kbs(kb_names: List[str]) -> List[Document]:
    """
    加载多个知识库，合并为一个文档列表。
    """
    all_docs = []
    for name in kb_names:
        file_path = STORAGE_DIR / f"{name}.json"
        if not file_path.exists():
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 将字典转回 Document 对象
        for item in data:
            all_docs.append(
                Document(page_content=item["page_content"], metadata=item["metadata"])
            )
            
    return all_docs


def delete_kb(kb_name: str):
    """删除指定知识库。"""
    file_path = STORAGE_DIR / f"{kb_name}.json"
    if file_path.exists():
        os.remove(file_path)