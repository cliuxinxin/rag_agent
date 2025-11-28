import os
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.nodes import get_llm

# === 0. 缓存感知 System Prompt (保持不变) ===
def get_cached_system_prompt(content: str) -> str:
    return f"""你是一个处于"DeepSeek Context Caching"模式下的顶级技术研究员。
以下是我们需要深度剖析的文档全文（已缓存），请仔细阅读每一个段落、公式、脚注和图表：

<DOCUMENT_START>
{content}
<DOCUMENT_END>
"""

# === 1. Planner Node: 自适应策划者 ===
def planner_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    loop = state.get("loop_count", 0)
    MAX_LOOPS = 4  # 稍微减少轮次，避免对简单文章过度分析
    
    llm = get_llm()
    
    history_text = "\n\n".join(qa_history) if qa_history else "暂无，这是第一轮。"
    
    # === 关键修改：通用化技术审查清单 ===
    task_prompt = f"""
    当前调研轮次: {loop + 1}/{MAX_LOOPS}
    
    【已有的调研片段】
    {history_text}
    
    【任务目标】
    你是技术侦探。请先判断文档类型（是 **学术论文** 还是 **工程/技术博客**？）。
    然后检查我们是否挖掘出了该类型文档的核心价值。
    
    请对照以下【通用深度清单】进行检查：
    
    1.  **如果是学术论文 (Academic Paper)**：
        - 核心创新点（Novelty）是什么？
        - 关键算法/架构的数学原理是什么？（找公式、找推导）
        - 实验对比数据是否详尽？
        
    2.  **如果是技术博客/工程实践 (Technical Blog/Project)**：
        - 核心方案选型（Hardware/Stack）的逻辑是什么？
        - 关键性能指标（Benchmarks/Cost）具体是多少？
        - 踩坑经验（Trade-offs）和避坑指南有哪些？
        
    【决策】
    - 如果还有模糊不清的技术细节（例如：具体的配置参数、特定的算法步骤、关键的测试数据），请提出**一个**具体问题。
    - 如果核心信息已收集完毕，输出 "TERMINATE"。
    
    只输出问题本身或 "TERMINATE"。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    response = llm.invoke(messages).content.strip()
    
    if "TERMINATE" in response or loop >= MAX_LOOPS:
        return {"next": "Writer", "current_question": ""}
    else:
        question = response.replace('"', '').replace("'", "")
        return {
            "next": "Researcher", 
            "current_question": question, 
            "loop_count": loop + 1
        }

# === 2. Researcher Node ===
def researcher_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    question = state["current_question"]
    
    llm = get_llm()
    
    task_prompt = f"""
    【待攻克的技术问题】
    {question}
    
    请基于全文进行回答。
    要求：
    1. **精准引用**：如果文中提到了具体的参数（如价格、型号）、代码片段、公式或数据，请原样摘录。
    2. **拒绝脑补**：文档里没说的，明确说“文中未提及”，不要强行编造公式或原理。
    3. **专家视角**：用技术人员的语言回答。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    answer = llm.invoke(messages).content
    
    qa_entry = f"❓ **Q**: {question}\n💡 **A**: {answer}"
    
    return {
        "qa_pairs": [qa_entry],
        "next": "Planner"
    }

# === 3. Writer Node: 自适应技术作家 ===
def writer_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    doc_title = state.get("doc_title", "文档")
    
    llm = get_llm()
    
    history_text = "\n\n".join(qa_history)
    
    # === 关键修改：动态分支 Prompt ===
    task_prompt = f"""
    我们已经完成了对《{doc_title}》的深度调研。
    
    【调研素材】
    {history_text}
    
    【任务】
    请根据文档的类型，选择最合适的报告结构，撰写一份**层层递进**的深度解读报告。
    
    ---
    
    ### 🛡️ 分支 A：如果是【学术论文】(AI, CS, Math)
    请使用以下结构：
    1. **直觉与核心洞察**：用通俗类比解释核心思想（如 Nesting, Attention）。
    2. **架构的系统视角**：解释模型组件（如 HOPE, Titans）。**必须包含 Mermaid 流程图**。
    3. **显微镜下的数学内核**：解释公式推导、优化器原理（如 Muon）。**使用 LaTeX 公式**。
    4. **关键实验数据**：SOTA 对比。
    
    ### 🛠️ 分支 B：如果是【工程/硬件/评测】(NAS, Coding, Tutorial)
    请使用以下结构：
    1. **项目背景与痛点**：作者为什么要对应这个问题？解决了什么核心冲突（如 功耗 vs 性能）？
    2. **系统架构与选型 (The Stack)**：
       - **硬件层**：主板、CPU、机箱、存储的分层设计。**请尝试用 Mermaid 画出硬件连接或数据流图**。
       - **软件层**：OS (TrueNAS)、文件系统 (ZFS) 配置。
    3. **深度性能/成本分析 (Deep Analysis)**：
       - **成本效益**：对比商业方案（如 QNAP/Synology）。
       - **基准测试 (Benchmarks)**：具体的 IOPS、吞吐量、功耗数据分析。不要编造公式，直接分析数据。
    4. **避坑与经验 (Lessons Learned)**：作者在构建过程中遇到了什么困难？（如线缆管理、驱动兼容性）。
    
    ---
    
    【通用排版要求】
    - 标题清晰，Markdown 格式。
    - 数学公式使用 LaTeX ($$...$$)。
    - Mermaid 代码块使用 ```mermaid ... ```。
    - 语气专业、客观。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    report = llm.invoke(messages).content
    
    return {
        "final_report": report,
        "next": "Outlooker"
    }

# === 4. Outlooker Node ===
def outlook_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    current_report = state["final_report"]
    
    llm = get_llm()
    
    task_prompt = f"""
    你是一个极具实践精神的技术顾问。
    请基于已生成的报告，根据文档类型，增加一个 **# 🚀 行动指南与扩展 (Actionable Outlook)** 章节。
    
    ### 如果是【学术论文】：
    1. **复现指引**：代码库推荐、难点预警。
    2. **变体实验**：如何修改架构做进一步研究？
    3. **延伸阅读**：推荐 2-3 篇前置理论论文。
    
    ### 如果是【工程/硬件项目】(如 DIY NAS)：
    1. **复刻指南**：如果读者想照着做，最难买的配件是什么？有没有替代品（更便宜或更强的方案）？
    2. **进阶优化**：在作者的基础上，还有什么可以改进的？（如：更强的散热、更省电的配置、万兆网卡升级）。
    3. **知识延伸**：为了玩转这个项目，读者还需要补什么课？（如 ZFS 调优指南、Docker 网络配置）。
    
    请输出 Markdown 文本，追加到报告末尾。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    outlook_content = llm.invoke(messages).content
    final_full_report = current_report + "\n\n" + outlook_content
    
    return {
        "final_report": final_full_report,
        "next": "END"
    }

# === 构建图 ===
def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("Planner", planner_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Writer", writer_node)
    workflow.add_node("Outlooker", outlook_node) # 新增节点

    workflow.set_entry_point("Planner")

    def route(state): return state["next"]

    workflow.add_conditional_edges(
        "Planner", route, 
        {"Researcher": "Researcher", "Writer": "Writer"}
    )
    
    workflow.add_edge("Researcher", "Planner")
    workflow.add_edge("Writer", "Outlooker") # Writer -> Outlooker
    workflow.add_edge("Outlooker", END)      # Outlooker -> END
    
    return workflow.compile()

deep_graph = build_graph()
