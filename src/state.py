from typing import List, TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
import operator

def add_messages(left: list, right: list):
    return left + right

def add_documents(left: list, right: list):
    """累加文档列表"""
    # 简单的去重逻辑：根据 content 去重
    existing_contents = {d.page_content for d in left}
    new_docs = []
    for d in right:
        if d.page_content not in existing_contents:
            new_docs.append(d)
            existing_contents.add(d.page_content)
    return left + new_docs

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str
    
    # 原始知识库
    source_documents: List[Document]
    vector_store: Any
    
    # 搜索指令
    current_search_query: str
    
    # === 新增：累积的证据 (原始文档) ===
    # 这样 Answerer 就能看到所有被 Searcher 找到的 Raw Docs
    final_evidence: Annotated[List[Document], add_documents]
    
    # === 新增：循环计数器 ===
    loop_count: int