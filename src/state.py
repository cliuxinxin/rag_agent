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

# === 新增：简单的列表追加逻辑 ===
def add_strings(left: list, right: list):
    if left is None: left = []
    if right is None: right = []
    return left + right

# === 新增：简单的列表替换逻辑 ===
def replace_list(old, new):
    """用于直接替换列表内容（针对 suggested_questions）"""
    return new

class AgentState(TypedDict):
    # === 基础字段 ===
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # === 深度模式通用字段 ===
    full_content: str        # 文档全文 (Context Caching 用)
    doc_title: str           # 文档标题
    
    # [新增] 仅用于深度问答模式：用户的核心问题
    user_goal: str           
    
    next: str                
    loop_count: int          
    
    current_question: str    # Agent 当前正在研究的子问题
    qa_pairs: Annotated[List[str], add_strings] # 积累的思考过程
    
    final_report: str        # 最终输出
    
    # [新增] 推荐的追问问题 (每次生成新的覆盖旧的)
    suggested_questions: Annotated[List[str], replace_list]
    
    # 原始知识库
    source_documents: List[Document]
    vector_store: Any
    
    # 搜索指令
    current_search_query: str
    
    # === 新增：累积的证据 (原始文档) ===
    # 这样 Answerer 就能看到所有被 Searcher 找到的 Raw Docs
    final_evidence: Annotated[List[Document], add_documents]
    
    # === 新增：循环计数器 ===
    # loop_count: int  # 已移到深度解读专用字段
    
    # === 新增：已尝试的搜索路径记忆 ===
    # 记录 Supervisor 曾经下达过的所有 search_query
    attempted_searches: Annotated[List[str], add_strings]
    
    # === 新增：记录搜不到的话题 ===
    # 记录明确搜索过但未找到内容的话题
    failed_topics: Annotated[List[str], add_strings]
    
    # === 新增：调查笔记本 ===
    # 每一轮 Searcher 会把"这一轮我发现了什么重要信息"记在这里
    # 格式建议： "Round 1 (Topic): Found X, Y, Z."
    research_notes: Annotated[List[str], add_strings]

# === [新增] 深度写作状态 ===
class WriterState(TypedDict):
    # === 基础配置 ===
    project_id: str
    user_requirement: str        # 用户需求
    kb_names: List[str]          # 知识库
    source_content: str          # 原始素材 (Context Caching)
    
    # === Agent 思考循环 (Planner -> Researcher) ===
    messages: Annotated[Sequence[BaseMessage], add_messages]
    loop_count: int
    current_question: str        # 当前调研的问题
    qa_pairs: Annotated[List[str], add_strings] # 积累的知识点
    
    # === 核心产物 ===
    research_report: str         # 调研报告 (Markdown)
    current_outline: List[dict]  # 大纲 (JSON)
    
    # === 正文生成 ===
    current_section_index: int   # 当前写第几章
    generated_content: str       # 已生成的全文 (用于上下文连贯)
    current_section_draft: str   # 当前这一章生成的草稿
    
    next: str
