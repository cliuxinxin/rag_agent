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
    messages: Annotated[Sequence[BaseMessage], add_messages]
    full_content: str
    doc_title: str
    user_goal: str
    next: str
    loop_count: int
    current_question: str
    qa_pairs: Annotated[List[str], add_strings]
    final_report: str
    suggested_questions: Annotated[List[str], replace_list]
    source_documents: List[Document]
    vector_store: Any
    current_search_query: str
    final_evidence: Annotated[List[Document], add_documents]
    attempted_searches: Annotated[List[str], add_strings]
    failed_topics: Annotated[List[str], add_strings]
    research_notes: Annotated[List[str], add_strings]
# === [新增] 深度写作状态 ===
class WriterState(TypedDict):
    project_id: str
    user_requirement: str
    source_type: str
    source_data: Any
    
    # === [新增] 全文缓存核心字段 ===
    full_content: str          # 用于 Context Caching 的全文内容
    
    # === 调研与大纲 ===
    planning_steps: List[str]
    research_notes: Annotated[List[str], add_strings]
    research_report: str
    current_outline: List[dict]
    
    # === 修改与迭代 ===
    edit_instruction: str
    full_draft: str
    current_section_index: int
    current_section_content: str
    social_summary: str
    
    # === 控制 ===
    loop_count: int
    next: str


# === [新增] DeepSeek Newsroom 专用状态 ===
class NewsroomState(TypedDict):
    # --- 身份标识 ---
    project_id: str         # [新增] 数据库中的项目ID，用于区分新建还是更新
    
    # === [新增] 搜索开关 ===
    enable_web_search: bool 

    # --- 静态缓存核心 ---
    full_content: str       # 原始素材（用于 Context Caching）
    user_requirement: str   # 用户原始需求

    # --- 阶段 1: 策划 ---
    generated_angles: List[dict]  # AI 生成的切入角度
    selected_angle: dict          # 用户或 AI 选定的角度

    # --- 阶段 2: 架构 ---
    outline: List[dict]           # 结构化大纲

    # --- 阶段 3: 采编与撰写 (循环) ---
    current_section_index: int
    section_drafts: List[str]
    research_cache: str

    # --- 阶段 4: 审阅与定稿 ---
    full_draft: str
    critique_notes: str
    final_article: str

    # --- 控制 ---
    loop_count: int
    next: str
