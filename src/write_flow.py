import json
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes import get_llm
from src.storage import load_kbs
from langchain_community.retrievers import BM25Retriever

# === 节点 1: 调研员 (Researcher) ===
def writing_research_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    kb_names = state.get("kb_names", [])
    source_content = state.get("source_content", "")
    
    llm = get_llm()
    
    context = ""
    
    # 1. 如果有知识库，进行检索
    if kb_names:
        docs, _ = load_kbs(kb_names)
        if docs:
            # 简单检索：提取关键词 -> BM25
            # 为了省事，直接把 Top N 文档塞进去，或者让 LLM 先生成关键词再搜
            # 这里简化：直接让 LLM 基于需求生成 3 个关键词，然后搜
            kw_prompt = f"请针对写作需求 '{req}'，提取3个最重要的搜索关键词，用空格分隔。"
            keywords = llm.invoke([HumanMessage(content=kw_prompt)]).content
            
            retriever = BM25Retriever.from_documents(docs)
            retriever.k = 8
            results = retriever.invoke(f"{req} {keywords}")
            
            context += "\n【知识库参考资料】\n"
            for i, doc in enumerate(results):
                context += f"[Ref {i+1}] {doc.page_content[:300]}...\n"

    # 2. 如果有上传文本
    if source_content:
        context += f"\n【上传文档内容】\n{source_content[:5000]}..." # 截断防止过长

    # 3. 生成调研报告
    report_prompt = f"""
    你是一个专业的内容策划专家。
    写作任务：{req}
    
    参考资料：
    {context}
    
    请根据任务和资料，写一份简短的【写作调研报告】（500字以内）：
    1. 核心主题是什么？
    2. 目标受众是谁？
    3. 关键素材有哪些？
    4. 建议的文章基调（Tone）。
    """
    
    report = llm.invoke([HumanMessage(content=report_prompt)]).content
    
    return {
        "research_summary": report,
        "source_content": context, # 更新 context 以便后续使用
        "next": "OutlineGenerator"
    }

# === 节点 2: 大纲生成器 (OutlineGenerator) ===
def outline_generator_node(state: WriterState) -> dict:
    req = state["user_requirement"]
    report = state["research_summary"]
    
    llm = get_llm()
    
    # 强制输出 JSON 格式
    prompt = f"""
    基于以下调研报告，为该文章生成一份详细的大纲。
    
    【任务】{req}
    【调研】{report}
    
    请严格按照以下 JSON 格式输出（不要包含 Markdown 代码块标记，只输出 JSON）：
    [
        {{
            "title": "第一章标题",
            "desc": "本章主要内容简述，包含的关键点",
            "content": "" 
        }},
        {{
            "title": "第二章标题",
            ...
        }}
    ]
    
    要求：
    1. 逻辑清晰，层层递进。
    2. 至少包含 4-6 个章节。
    3. desc 字段要详细，用于指导后续 AI 写作。
    """
    
    res = llm.invoke([HumanMessage(content=prompt)]).content
    clean_json = res.replace("```json", "").replace("```", "").strip()
    
    try:
        outline = json.loads(clean_json)
    except:
        # 容错：如果解析失败，生成一个简单的默认大纲
        outline = [{"title": "解析失败", "desc": "请重试或手动编辑", "content": ""}]
    
    return {
        "current_outline": outline,
        "next": "END"
    }

# === 节点 3: 大纲修改器 (OutlineRefiner) ===
def outline_refiner_node(state: WriterState) -> dict:
    current_outline = state["current_outline"]
    instruction = state["edit_instruction"]
    
    llm = get_llm()
    
    prompt = f"""
    你是一个大纲编辑。
    
    【当前大纲 (JSON)】
    {json.dumps(current_outline, ensure_ascii=False)}
    
    【修改指令】
    {instruction}
    
    请根据指令修改大纲，并输出新的 JSON。
    保持原有格式：List[Dict]，包含 title, desc, content(保持为空)。
    只输出 JSON。
    """
    
    res = llm.invoke([HumanMessage(content=prompt)]).content
    clean_json = res.replace("```json", "").replace("```", "").strip()
    
    try:
        new_outline = json.loads(clean_json)
    except:
        new_outline = current_outline # 失败则不改
        
    return {"current_outline": new_outline, "next": "END"}

# === 节点 4: 章节写作者 (SectionWriter) ===
def section_writer_node(state: WriterState) -> dict:
    outline = state["current_outline"]
    idx = state["current_section_index"]
    report = state["research_summary"]
    context = state["source_content"] # 包含检索到的 KB 片段
    
    if idx < 0 or idx >= len(outline):
        return {"generated_section_content": "", "next": "END"}
    
    target_section = outline[idx]
    
    llm = get_llm()
    
    prompt = f"""
    你是一个专业的作家。请根据大纲和背景资料，撰写文章的其中一章。
    
    【文章调研背景】
    {report}
    
    【参考资料片段】
    {context[:2000]}
    
    【当前章节要求】
    标题：{target_section['title']}
    内容要点：{target_section['desc']}
    
    【写作要求】
    1. 使用 Markdown 格式。
    2. 内容充实，紧扣要点。
    3. 风格需要连贯。
    4. 直接输出正文，不要重复标题。
    """
    
    content = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {"generated_section_content": content, "next": "END"}

# === 构建图 ===

# 1. 生成大纲的图
def build_outline_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Researcher", writing_research_node)
    wf.add_node("OutlineGenerator", outline_generator_node)
    
    wf.set_entry_point("Researcher")
    wf.add_edge("Researcher", "OutlineGenerator")
    wf.add_edge("OutlineGenerator", END)
    return wf.compile()

# 2. 修改大纲的图
def build_refine_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Refiner", outline_refiner_node)
    wf.set_entry_point("Refiner")
    wf.add_edge("Refiner", END)
    return wf.compile()

# 3. 写作的图
def build_writing_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Writer", section_writer_node)
    wf.set_entry_point("Writer")
    wf.add_edge("Writer", END)
    return wf.compile()

outline_graph = build_outline_graph()
refine_graph = build_refine_graph()
writing_graph = build_writing_graph()