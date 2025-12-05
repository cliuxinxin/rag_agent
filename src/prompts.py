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