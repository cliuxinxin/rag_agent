# src/prompts.py

def get_context_caching_system_prompt(content: str) -> str:
    return f"""你是一个处于"DeepSeek Context Caching"模式下的顶级专家。
以下是我们需要深度处理的文档全文（已缓存），请仔细阅读每一个段落：

<DOCUMENT_START>
{content}
<DOCUMENT_END>
"""

# === 深度阅读 (Deep Read) ===

def get_read_planner_prompt(loop: int, max_loops: int, history_text: str) -> str:
    return f"""
    当前分析轮次: {loop + 1}/{max_loops}
    
    【我们已有的理解（已解决的问题）】
    {history_text}
    
    【任务目标】
    请先快速通读全文，判断文章体裁。
    然后，提出下一个最值得挖掘的**"深度问题"**。
    
    【输出要求】
    - 如果你觉得文章的核心逻辑、关键决策、深层含义都已经分析透彻了，输出 "TERMINATE"。
    - 否则，输出**一个**具体的、有深度的问题。
    """

def get_read_writer_prompt(doc_title: str, history_text: str) -> str:
    return f"""
    我们已经完成了对《{doc_title}》的深度阅读。
    
    【深度思考素材（Q&A 记录）】
    {history_text}
    
    【写作任务】
    请根据文档类型，利用上述素材，撰写一份**深度导读与分析报告**。
    请自适应选择结构（纪实故事 vs 技术文档）。
    标题自拟，具有吸引力。
    """

# === 深度写作 (Writing) ===

def get_writer_iteration_prompt(idx: int, title: str, report: str, desc: str, context: str) -> str:
    return f"""
    你是一位追求完美的科技专栏主编。
    正在撰写文章的第 {idx + 1} 部分，章节标题为：【{title}】。
    
    【核心素材 (Fact Base)】
    {report}
    
    【本章写作指引】
    {desc}
    
    【上文脉络 (Context)】
    {context[-4000:]} 
    
    【写作要求】
    - 禁止重复标题，直接写正文。
    - 语气专业、客观、有深度。
    - 开头必须自然承接上文脉络。
    """

# === 深度问答 (Deep QA) ===

def get_qa_planner_prompt(loop: int, max_loops: int, user_goal: str, history_text: str) -> str:
    return f"""
    当前思考轮次: {loop + 1}/{max_loops}
    
    【用户提出的核心问题】
    "{user_goal}"
    
    【我们已从文中查证的信息】
    {history_text}
    
    【任务目标】
    你的唯一目标是完整、准确地回答用户的核心问题。
    请判断：基于【已查证的信息】，我们是否已经能完美回答这个问题？
    
    - 如果还缺信息（例如用户问对比，但我们只查了A方），请提出下一个**具体的子问题**。
    - 如果用户问的是细节（如数据），请通过子问题反复确认上下文。
    
    【输出要求】
    - 如果信息已充足，请直接输出 "TERMINATE"。
    - 否则，输出一个**为了回答核心问题必须搞清楚的子问题**。
    """

def get_qa_writer_prompt(doc_title: str, user_goal: str, history_text: str) -> str:
    return f"""
    我们针对文档《{doc_title}》进行了针对性的深度调研。
    
    【用户提问】
    {user_goal}
    
    【调研过程与发现】
    {history_text}
    
    【任务】
    请基于上述调研发现，撰写最终回答。
    
    【要求】
    1. **直击痛点**：第一句话直接给出核心结论。
    2. **证据确凿**：引用文中的具体段落或数据来支持你的观点（基于调研发现）。
    3. **逻辑闭环**：如果文中没有直接答案，请根据文中的线索进行合理推断，并注明这是推断。
    4. 不要写成"导读"或"读后感"，要写成专业的"答案"。
    """


# =========================================================
# === DeepSeek Newsroom (Deep Writing 2.0) Prompts ===
# =========================================================


def get_newsroom_base_prompt(content: str, requirement: str) -> str:
    """
    核心缓存块：包含文档全文和用户需求。
    所有 Newsroom 的 Agent 必须以此为开头，以命中缓存。
    """
    return f"""
<DOCUMENT_CACHE_START>
{content}
<DOCUMENT_CACHE_END>

<USER_REQUIREMENT>
{requirement}
</USER_REQUIREMENT>

你现在的身份是【DeepSeek 新闻工作室】的成员。
所有的工作必须严格基于 <DOCUMENT_CACHE> 中的内容，严禁编造事实。
"""


def get_angle_generator_prompt() -> str:
    return """
    【任务：选题策划】
    作为首席策划，请基于文档内容和用户需求，构思 3 个截然不同的写作切入角度（Angle）。
    
    1. **深度解析型**：侧重逻辑、原理和深度分析。
    2. **故事叙述型**：侧重人物、时间线和冲突细节。
    3. **观点评论型**：侧重提炼核心观点，进行批判或赞赏。
    
    请输出 JSON 格式：
    [
        {"title": "...", "desc": "...", "reasoning": "..."},
        ...
    ]
    """


def get_outline_architect_prompt(angle: str) -> str:
    return f"""
    【任务：大纲构建】
    用户选定的切入角度是：【{angle}】。
    作为架构师，请制定一份详细的**结构化大纲**。
    
    要求：
    1. 包含 4-8 个章节。
    2. 每一章必须明确 "主旨 (Gist)" 和 "需引用的核心事实/数据 (Key Facts)"。
    3. 逻辑流畅，符合选定的切入角度。
    
    请输出 JSON 格式：
    [
        {{"title": "...", "gist": "本段核心讲...", "key_facts": "引用文档中关于xxx的数据..."}},
        ...
    ]
    """


def get_internal_researcher_prompt(section_title: str, key_facts_needed: str) -> str:
    return f"""
    【任务：内部采编】
    我们要写章节：【{section_title}】
    需要用到的素材线索：{key_facts_needed}
    
    请作为“内部探员”，在 <DOCUMENT_CACHE> 中**逐字逐句**检索相关信息。
    提取出最精准的原文引用、数据或案例。如果文档里没有，请明确说明“无相关记录”。
    
    输出格式：
    - **事实 1**: ... (原文引用)
    - **事实 2**: ... (原文引用)
    - **推论**: ... (基于原文的合理推断)
    """


def get_section_drafter_prompt(section_title: str, research_notes: str, prev_context: str) -> str:
    return f"""
    【任务：章节撰写】
    当前章节：【{section_title}】
    
    【采编提供的核实素材】
    {research_notes}
    
    【前文脉络（保持连贯性）】
    ...{prev_context[-1000:]}
    
    请撰写本章正文。
    要求：
    1. **Show, Don't Tell**：多用素材中的细节，少用空洞的形容词。
    2. **风格统一**：保持专业且吸引人的笔触。
    3. **禁止**：不要写“综上所述”、“本章将讨论”，直接进入内容。
    4. 长度适中（300-600字）。
    """


def get_editor_reviewer_prompt(full_draft: str) -> str:
    return f"""
    【任务：主编审阅】
    以下是小编提交的初稿：
    
    <DRAFT_START>
    {full_draft}
    <DRAFT_END>
    
    作为毒舌主编，请提出修改意见。关注：
    1. **逻辑断层**：段落之间是否生硬？
    2. **废话过多**：是否有很多正确的废话？
    3. **语气**：是否符合用户最初的需求？
    
    请输出一段具体的“审阅意见（Critique Notes）”，指导润色师进行修改。不要直接改写，只给意见。
    """


def get_final_polisher_prompt(full_draft: str, critique_notes: str) -> str:
    return f"""
    【任务：最终润色】
    
    【初稿】
    {full_draft}
    
    【主编意见】
    {critique_notes}
    
    请作为金牌润色师，根据意见对初稿进行**全文重写或精修**。
    输出最终成稿（Markdown格式）。标题要足够吸引人。
    """