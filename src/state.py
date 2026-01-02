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
    # [新增] 动态知识库画像：Agent 会把从文档里看到的特征记在这里
    kb_summary: str
    # [新增] 知识库名称列表：用于采样和上下文对齐
    kb_names: List[str]
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
    project_id: str
    
    # === [新增] 搜索开关 ===
    enable_web_search: bool 

    # --- 静态缓存核心 ---
    full_content: str       # 原始素材

    # === [修改] 结构化需求替代原有的 user_requirement (保留该字段做兼容，但主要用下面的) ===
    user_requirement: str   # 汇总后的需求字符串（供通用 Prompt 使用）
    
    # [新增] 细分配置
    style_tone: str         # 语调/身份 (如：深度技术、幽默科普)
    article_length: str     # 篇幅 (如：短讯、长文)
    must_haves: str         # 必须包含的要素

    # --- 阶段 1: 策划 ---
    generated_angles: List[dict]  # AI 生成的切入角度
    selected_angle: dict          # 用户或 AI 选定的角度

    # --- 阶段 2: 架构 ---
    outline: List[dict]           # 结构化大纲
    
    # [新增] 大纲修改反馈
    user_feedback_on_outline: str # 用户对大纲的修改意见

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
    
    # === [新增] 用于 UI 显示过程 ===
    # 用于存储策划阶段搜到的背景信息
    macro_search_context: str 
    # 用于实时传回 Log (例如: "正在搜索 xxx...")，使用 add_strings 自动累加
    run_logs: Annotated[List[str], add_strings]

# === [新增] PPT 生成状态 ===
class PPTState(TypedDict):
    full_content: str
    doc_title: str
    slides_count: int
    ppt_outline: list # 策划阶段产生的中间态
    final_ppt_content: list # 最终用于渲染的 JSON
    
    # === 修改这里 ===
    # 之前是 ppt_file_path: str
    ppt_binary: bytes 
    # ================
    
    run_logs: Annotated[List[str], add_strings]
