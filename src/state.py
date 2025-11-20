"""src/state.py"""

from typing import List, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
import operator

def add_messages(left: list, right: list):
    """简单的消息追加合并逻辑"""
    return left + right

class AgentState(TypedDict):
    """
    Supervisor 架构的状态定义。
    """
    # 对话历史：包含 UserMessage, AIMessage (Supervisor/Answerer), FunctionMessage (Searcher results)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # 路由控制：指示下一个执行的节点
    next: str
    
    # 上下文数据
    source_documents: List[Document] # 原始知识库
    
    # 临时传递：Supervisor 指派给 Searcher 的具体搜索指令
    current_search_query: str