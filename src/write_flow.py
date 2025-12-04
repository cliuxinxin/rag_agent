import json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes import get_llm
from src.storage import load_kbs
from langchain_community.retrievers import BM25Retriever

# ==========================================
# PART 1: 调研与大纲生成 Agent
# ==========================================

def plan_node(state: WriterState) -> dict:
    """规划师：分析需求或现有大纲，决定需要调研什么方向"""
    req = state["user_requirement"]
    outline = state.get("current_outline", [])
    loop = state.get("loop_count", 0)
    
    # 限制调研轮次（例如最多查 3 次）
    if loop >= 3:
        return {"next": "ReportGenerator"}

    llm = get_llm()
    
    # 如果已有大纲（说明是修改后重新调研），则基于大纲规划
    if outline:
        outline_str = "\n".join([f"- {item['title']}: {item['desc']}" for item in outline])
        prompt = f"""
        当前任务：完善写作项目的调研。
        用户需求：{req}
        当前大纲：
        {outline_str}
        
        请分析大纲中哪些部分缺乏事实支撑？提出 2-3 个具体的搜索关键词或问题，用于补充调研。
        """
    else:
        # 第一次生成，基于需求规划
        prompt = f"""
        当前任务：为写作项目做前期调研。
        用户需求：{req}
        
        请分析为了写好这篇文章，我们需要搜集哪些核心信息？
        请输出 2-3 个具体的搜索关键词或方向。
        """
    
    # 这里简化处理，直接让 LLM 输出关键词，实际可以做成 Structured Output
    plan = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {
        "planning_steps": [plan],
        "next": "Researcher",
        "loop_count": loop + 1
    }

def research_node(state: WriterState) -> dict:
    """研究员：执行搜索"""
    source_type = state["source_type"]
    source_data = state["source_data"]
    plans = state.get("planning_steps", [])
    latest_plan = plans[-1] if plans else ""
    
    # 1. 获取上下文（知识库检索 或 静态文本）
    retrieved_text = ""
    
    if source_type == "kb":
        # 解析 KB 列表
        try:
            kb_list = json.loads(source_data) if isinstance(source_data, str) else source_data
            docs, _ = load_kbs(kb_list)
            if docs:
                # 基于 Plan 进行检索
                retriever = BM25Retriever.from_documents(docs)
                retriever.k = 5
                # 简单提取 Plan 中的关键词进行检索
                results = retriever.invoke(latest_plan)
                retrieved_text = "\n".join([f"[KB Ref] {d.page_content}" for d in results])
        except Exception as e:
            print(f"Research Error: {e}")
            
    elif source_type in ["file", "text"]:
        # 对于上传文件，全文作为上下文（如果不长），或者做简单切片检索
        # 这里为了简单，假设 text 模式下 source_data 就是全文
        full_text = source_data
        if len(full_text) > 10000:
            # 简单截断或做简单查找
            retrieved_text = full_text[:10000] 
        else:
            retrieved_text = full_text

    if not retrieved_text:
        retrieved_text = "未找到相关资料。"

    # 2. 总结发现
    llm = get_llm()
    summary_prompt = f"""
    根据搜索计划：{latest_plan}
    我们检索到了以下内容：
    {retrieved_text[:3000]}
    
    请提取对写作有帮助的事实、数据或观点，形成一条调研笔记。
    """
    note = llm.invoke([HumanMessage(content=summary_prompt)]).content
    
    return {
        "research_notes": state.get("research_notes", []) + [note],
        "next": "PlanCheck" # 搜完一次，回去检查是否还需要搜
    }

def plan_check_node(state: WriterState) -> dict:
    """简单的循环控制器"""
    loop = state.get("loop_count", 0)
    # 比如我们硬性规定搜 2 轮就够了
    if loop >= 2:
        return {"next": "ReportGenerator"}
    return {"next": "Planner"} # 回去 Planner 继续规划

def report_node(state: WriterState) -> dict:
    """报告生成器：汇总所有笔记"""
    req = state["user_requirement"]
    notes = state.get("research_notes", [])
    
    llm = get_llm()
    
    notes_text = "\n\n".join(notes)
    
    prompt = f"""
    你是一个高级分析师。
    
    【写作需求】{req}
    【累计调研笔记】
    {notes_text}
    
    请根据以上信息，撰写一份结构清晰的《深度调研报告》。
    包含：核心主旨、关键论据、素材储备、建议的叙事角度。
    """
    
    report = llm.invoke([HumanMessage(content=prompt)]).content
    return {"research_report": report, "next": "Outliner"}

def outline_node(state: WriterState) -> dict:
    """大纲生成器：增强容错能力"""
    req = state["user_requirement"]
    report = state["research_report"]
    
    llm = get_llm()
    
    prompt = f"""
    基于调研报告，设计文章大纲。
    
    【需求】{req}
    【报告】{report[:3000]} 
    
    请输出严格的 JSON 格式（List[Dict]），包含 title, desc。
    不要输出任何 Markdown 标记（如 ```json），只输出纯 JSON 文本。
    
    示例格式：
    [
        {{"title": "第一章：...", "desc": "..."}},
        {{"title": "第二章：...", "desc": "..."}}
    ]
    """
    
    res = llm.invoke([HumanMessage(content=prompt)]).content
    
    # === 增强清洗逻辑 ===
    clean_json = res.replace("```json", "").replace("```", "").strip()
    # 有时候 LLM 会在开头加 "Here is the json..."，我们要尝试找到第一个 [
    start_idx = clean_json.find("[")
    end_idx = clean_json.rfind("]")
    
    new_outline = []
    
    if start_idx != -1 and end_idx != -1:
        clean_json = clean_json[start_idx : end_idx + 1]
        try:
            new_outline = json.loads(clean_json)
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}")
            # 降级策略：如果解析失败，创建一个单章提示
            new_outline = [{"title": "大纲解析失败", "desc": f"原始内容：{clean_json[:100]}..."}]
    else:
         new_outline = [{"title": "生成格式错误", "desc": "AI 未返回有效的 JSON 格式。"}]

    return {"current_outline": new_outline, "next": "END"}

# ==========================================
# PART 2: 迭代写作 Agent
# ==========================================

def iterative_writer_node(state: WriterState) -> dict:
    """
    迭代写作者：
    输入：调研报告 + 完整大纲 + 之前写好的所有正文(Context) + 当前章节要求
    """
    report = state["research_report"]
    outline = state["current_outline"]
    idx = state["current_section_index"]
    # full_draft 存储的是之前所有章节合并的文本，或者我们可以从 DB 读
    # 这里假设 state 里传进来了之前已生成的内容
    previous_context = state.get("full_draft", "")
    
    if idx < 0 or idx >= len(outline):
        return {"current_section_content": "", "next": "END"}
    
    target_section = outline[idx]
    
    llm = get_llm()
    
    # 构造新的“主编级” Prompt
    prompt = f"""
    你是一位顶级科技媒体（如《晚点LatePost》、《机器之心》）的资深主编。
    你的任务是基于调研报告和大纲，撰写文章的第 {idx + 1} 部分。
    
    【核心调研报告】
    {report}
    
    【当前章节信息】
    标题：{target_section['title']}
    写作指引：{target_section['desc']}
    
    【上文脉络 (Context)】
    {previous_context[-3000:]}
    (请确保与上文逻辑连贯，不要重复上文已讲过的信息)
    
    【写作核心指令 (必读)】
    1. **身份设定**：你不是写报告的机器人，你是洞察力极强的行业观察者。语气要客观犀利，拒绝平铺直叙。
    2. **叙事张力**：
       - 如果是开头，请通过行业痛点或巨大反差制造悬念。
       - 如果是技术解析，请使用**通俗类比**（例如：将DSA比作“速读术”，将强化学习比作“题海战术”）。
    3. **深度洞察**：不要只罗列数据。要分析数据背后的“二阶效应”（例如：技术突破对商业模式的毁灭性打击，对闭源模型的倒逼）。
    4. **格式规范**：
       - **禁止**使用“第一章”、“第二章”这种教科书式标题，直接使用具有吸引力的新闻式小标题（Markdown二级标题）。
       - 适当使用引用块（> 引用）来强调核心金句。
       - 对比数据请尽量使用 Markdown 表格。
    
    请直接输出正文内容。
    """
    
    content = llm.invoke([HumanMessage(content=prompt)]).content
    
    return {"current_section_content": content, "next": "END"}

# ==========================================
# 构建图
# ==========================================

# 1. 调研与大纲图 (Research & Outline Flow)
def build_research_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Planner", plan_node)
    wf.add_node("Researcher", research_node)
    wf.add_node("PlanCheck", plan_check_node)
    wf.add_node("ReportGenerator", report_node)
    wf.add_node("Outliner", outline_node)
    
    # 逻辑：Planner -> Researcher -> PlanCheck -> (Loop Planner OR ReportGenerator)
    wf.set_entry_point("Planner")
    
    wf.add_edge("Planner", "Researcher")
    wf.add_edge("Researcher", "PlanCheck")
    
    wf.add_conditional_edges(
        "PlanCheck",
        lambda x: x["next"],
        {"Planner": "Planner", "ReportGenerator": "ReportGenerator"}
    )
    
    wf.add_edge("ReportGenerator", "Outliner")
    wf.add_edge("Outliner", END)
    
    return wf.compile()

# 2. 写作图 (Drafting Flow)
def build_drafting_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Writer", iterative_writer_node)
    wf.set_entry_point("Writer")
    wf.add_edge("Writer", END)
    return wf.compile()

# 新增：大纲修改节点
def outline_refiner_node(state: WriterState) -> dict:
    current_outline = state["current_outline"]
    instruction = state.get("edit_instruction", "")
    
    llm = get_llm()
    
    # 转换为字符串以便 LLM 理解上下文
    outline_str = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    prompt = f"""
    你是一个专业的主编。请根据修改指令调整文章大纲。
    
    【当前大纲】
    {outline_str}
    
    【修改指令】
    {instruction}
    
    【任务要求】
    1. 请严格输出修改后的 JSON 数据（List[Dict]）。
    2. 保持 JSON 结构包含：title, desc, content (保持原样或为空)。
    3. 严禁输出 Markdown 标记（如 ```json），只输出纯 JSON。
    4. 如果是增加章节，请生成合理的 desc。
    """
    
    res = llm.invoke([HumanMessage(content=prompt)]).content
    
    # === 增强清洗逻辑 (关键修复) ===
    clean_json = res.replace("```json", "").replace("```", "").strip()
    
    # 尝试寻找 JSON 数组的边界
    start_idx = clean_json.find("[")
    end_idx = clean_json.rfind("]")
    
    if start_idx != -1 and end_idx != -1:
        clean_json = clean_json[start_idx : end_idx + 1]
        try:
            new_outline = json.loads(clean_json)
        except json.JSONDecodeError:
            # 解析失败，回退到原大纲，避免清空数据
            print("Refine JSON Error, rollback.")
            new_outline = current_outline
    else:
        # 格式错误，回退
        new_outline = current_outline
        
    return {"current_outline": new_outline, "next": "END"}

# 3. 大纲修改图 (Outline Refinement Flow)
def build_refine_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Refiner", outline_refiner_node)
    wf.set_entry_point("Refiner")
    wf.add_edge("Refiner", END)
    return wf.compile()

# 导出
research_graph = build_research_graph()
drafting_graph = build_drafting_graph()
refine_graph = build_refine_graph()
