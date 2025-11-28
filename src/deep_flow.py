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

# === 1. Planner Node: 带着"审查清单"的策划者 ===
def planner_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    loop = state.get("loop_count", 0)
    MAX_LOOPS = 6  #稍微增加一轮，确保挖得深
    
    llm = get_llm()
    
    history_text = "\n\n".join(qa_history) if qa_history else "暂无，这是第一轮。"
    
    # === 关键修改：植入技术审查清单 ===
    task_prompt = f"""
    当前调研轮次: {loop + 1}/{MAX_LOOPS}
    
    【已有的调研片段】
    {history_text}
    
    【你的目标】
    我们要产出一份能达到 NeurIPS/ICLR 审稿人级别的深度解读报告。
    请检查我们目前的理解是否涵盖了以下【深度清单】：
    
    1. 🏗 **架构细节**：不仅仅是名字，是否搞懂了组件的具体运作？（例如：HOPE 到底是由哪两部分组成的？Titans 和 CMS 怎么分工？）
    2. 🧮 **数学本质**：文中是否将现有算法（如 Momentum, Adam）重新解释为了别的概念（如 Associative Memory）？有没有提到具体的数学联系（例如 Newton-Schulz 迭代、Muon 优化器）？
    3. 📉 **核心理论**：什么是 "Context Flow"？什么是 "Local Surprise Signal"？不要只看字面意思，要理解其物理含义。
    4. 📊 **实证数据**：不要只说"效果好"，要在具体参数量（如 1.3B）上对比它和 Transformer++、Mamba 的数据差异。
    
    【决策】
    - 如果上述清单中有任何一点模糊，请提出一个**极其具体、硬核**的问题。
      (错误示范："HOPE是什么？")
      (正确示范："文中提到的 Continuum Memory System 具体是如何通过不同频率的 MLP 链来实现的？与 Titans 模块如何协作？")
      (正确示范："文中提到 Momentum 加上非线性激活后等价于什么优化器？Muon 或者是 Newton-Schulz 在哪里被提及？")
      
    - 如果信息已完全从原文中挖掘殆尽，输出 "TERMINATE"。
    
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
        print(f"🧐 Planner (深度模式) 提出问题: {question}")
        return {
            "next": "Researcher", 
            "current_question": question, 
            "loop_count": loop + 1
        }

# === 2. Researcher Node: 精确引用的回答者 ===
def researcher_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    question = state["current_question"]
    
    llm = get_llm()
    
    # === 关键修改：要求引用原文细节 ===
    task_prompt = f"""
    【待攻克的技术问题】
    {question}
    
    请基于全文进行回答。
    要求：
    1. **不要模糊概括**：如果文中提到了具体的公式（如 Eq. 24）、具体的算法名（如 Muon）、具体的层级结构，必须明确写出。
    2. **引用原文**：如果可能，请简要引用原文的关键句子或数据来支持你的解释。
    3. **解释深度**：假设提问者是该领域的专家，不要使用过于浅显的科普语言，要精准。
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

# === 3. Writer Node: 层层递进的技术作家 ===
def writer_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    doc_title = state.get("doc_title", "文档")
    
    llm = get_llm()
    
    history_text = "\n\n".join(qa_history)
    
    # === 关键修改：三级放大镜写作结构 ===
    task_prompt = f"""
    我们已经完成了对《{doc_title}》的深度调研。
    
    【调研素材】
    {history_text}
    
    【任务】
    请撰写一份**层层递进**的深度解读报告。
    写作目标：让读者像剥洋葱一样，先理解直觉，再理解架构，最后掌握数学细节。
    
    请严格按照以下**三层结构**撰写：
    
    ---
    
    # 第一层：💡 直觉与核心洞察 (The Intuition)
    **目标用户**：希望快速抓住本质的非专家。
    **写作要求**：
    1.  **核心痛点**：用文中提到的"顺行性遗忘症"(Anterograde Amnesia) 类比，解释为什么现有 LLM 是静态的？
    2.  **Nested Learning 的通俗解释**：不要用公式。用"多重时间尺度"或"大脑记忆巩固"的类比，解释嵌套学习是什么。
    3.  **一句话总结创新**：HOPE 架构到底解决了什么问题？
    
    ---
    
    # 第二层：⚙️ 架构的系统视角 (The System View)
    **目标用户**：需要理解模型运作机理的工程师。
    **写作要求**：
    1.  **HOPE 的双引擎**：清晰解释 **Titans** (负责什么？) 和 **Continuum Memory System (CMS)** (负责什么？) 的分工。
    2.  **快慢系统的配合**：解释高频更新(Working Memory)和低频更新(Long-term Memory)是如何协作的。
    3.  **数据流向**：数据是如何流经这些嵌套的 MLP 链的？
    
    ---
    
    # 第三层：🔬 显微镜下的数学内核 (The Mathematical Core)
    **目标用户**：追求极致细节的研究员。
    **写作要求**：
    1.  **从 SGD 到 关联记忆**：详细解释公式推导，说明为什么优化器本质上是在做 Key-Value 映射？
    2.  **Continuum Memory 的数学实现**：**必须展示**不同频率更新的公式(例如 Eq. 31)，并解释 $C^{{(\ell)}}$ 的含义。
    3.  **优化器的深层彩蛋**：**详细阐述**文中关于 Momentum + Newton-Schulz 非线性 = **Muon 优化器** 的数学等价性。这是展示深度的关键点。
    
    ---
    
    # 📉 关键结论 (Key Takeaways)
    简要列出 1.3B 参数下的核心实验数据对比，证明这套理论行之有效。
    
    【排版要求】
    - 使用清晰的 Markdown 标题。
    - 数学公式请使用 LaTeX 格式(行内用 $...$, 独立块用 $$...$$)。
    - 语气要专业、流畅、引人入胜。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    report = llm.invoke(messages).content
    
    # 只需要修改最后返回的 next
    return {
        "final_report": report, # 这是之前的报告内容
        "next": "Outlooker"     # <--- 指向新节点
    }

# === 4. 新增: Outlooker Node (扩展思考者) ===
def outlook_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    current_report = state["final_report"]
    doc_title = state.get("doc_title", "本文档")
    
    llm = get_llm()
    
    # Prompt 设计：行动导向
    task_prompt = f"""
    你是一个极具前瞻性的科研导师。
    我们刚刚完成了对《{doc_title}》的深度解读。
    
    【已有报告】
    （已生成，包含核心摘要、架构、数学原理等）
    
    【任务】
    请在现有报告的基础上，增加一个章节：**# 🚀 行动指南与扩展研究 (Actionable Outlook)**
    
    请思考以下问题并给出具体建议（不要泛泛而谈）：
    1.  **代码复现指引**：如果我要复现这个工作，最难的部分在哪里？有什么现成的库（如 PyTorch, JAX, Triton）可以利用？
    2.  **变体实验建议**：我可以尝试修改架构中的哪个部分来获得潜在提升？（例如：把文中提到的 X 换成 Y 会怎样？）
    3.  **阅读延伸**：为了深刻理解这篇文章，我必须去读哪 2-3 篇经典的"前置论文"？请给出论文题目和推荐理由。
    
    请输出一段 Markdown 文本，我将把它追加到最终报告的末尾。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    outlook_content = llm.invoke(messages).content
    
    # 将新内容追加到最终报告中
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
