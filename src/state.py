"""定义 LangGraph 的状态结构。"""

from typing import List, TypedDict, Optional
from langchain_core.documents import Document


class AgentState(TypedDict):
    """Agent 的运行状态。"""
    
    question: str
    # 原始知识库文档 (由前端传入)
    source_documents: List[Document]
    # 检索到的相关文档
    retrieved_documents: List[Document]
    # 最终生成的答案
    generation: str
    # 搜索重试次数
    search_count: int
    # 是否需要重新搜索标记
    search_needed: bool