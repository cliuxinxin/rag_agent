import os
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.nodes import get_llm

# === 0. 缓存感知 System Prompt (保持不变) ===
def get_cached_system_prompt(content: str) -> str:
    return f"""你是一个处于"DeepSeek Context Caching"模式下的顶级深度阅读专家。
以下是我们需要深度剖析的文档全文（已缓存），请仔细阅读每一个段落：

<DOCUMENT_START>
{content}
<DOCUMENT_END>
"""

# === 1. Planner Node: 真正的"阅读策略家" ===
# 改进点：具备了"通用阅读能力"，能处理叙事、新闻、评论等非技术文章
def planner_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    loop = state.get("loop_count", 0)
    MAX_LOOPS = 4 
    
    llm = get_llm()
    
    # 格式化已有的问答对，让 Planner 知道我们已经搞懂了什么
    history_text = "\n".join(qa_history) if qa_history else "（暂无，这是第一轮分析）"
    
    # === 核心修改：通用的深度阅读 Prompt ===
    # 这一步实现了您说的"粗略阅读并提出问题"
    task_prompt = f"""
    当前分析轮次: {loop + 1}/{MAX_LOOPS}
    
    【我们已有的理解（已解决的问题）】
    {history_text}
    
    【任务目标】
    请先快速通读全文，判断文章体裁（是技术文档、纪实叙事、新闻报道，还是观点评论？）。
    然后，提出下一个最值得挖掘的**"深度问题"**。
    
    【提问策略】
    不要问浅显的事实（如"作者是谁？"），要问需要**结合原文与常识**才能回答的问题：
    
    1.  **如果是【纪实/叙事】（如：《流感下的北京中年》）**：
        - 关注**因果链与决策点**：例如"为什么文中提到的某个决定导致了后续的崩盘？常识上应该怎么做？"
        - 关注**资源与博弈**：例如"在资源（如ICU、金钱）受限时，主角面临了什么样的人性考验？"
        
    2.  **如果是【观点/评论】**：
        - 关注**逻辑漏洞与底层假设**：作者基于什么预设前提？这些前提在现实中成立吗？
        
    3.  **如果是【技术/科普】**：
        - 关注**核心原理与应用边界**：这个技术解决了什么本质问题？有什么代价？
        
    【输出要求】
    - 如果你觉得文章的核心逻辑、关键决策、深层含义都已经分析透彻了，输出 "TERMINATE"。
    - 否则，输出**一个**具体的、有深度的问题。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    response = llm.invoke(messages).content.strip()
    
    # 清理一下引号
    question = response.replace('"', '').replace("'", "")
    
    if "TERMINATE" in response or loop >= MAX_LOOPS:
        # 如果分析完了，转交给作家进行综合输出
        return {"next": "Writer", "current_question": ""}
    else:
        # 还有问题没搞懂，交给研究员去查
        return {
            "next": "Researcher", 
            "current_question": question, 
            "loop_count": loop + 1
        }

# === 2. Researcher Node: 结合常识的解答者 ===
# 改进点：明确要求"结合常识"进行解答
def researcher_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    question = state["current_question"]
    
    llm = get_llm()
    
    task_prompt = f"""
    【当前待攻克的问题】
    {question}
    
    【回答要求】
    你不仅仅是一个摘录机器，你是一个有智慧的分析师。请按以下步骤回答：
    
    1.  **原文证据**：首先，从文中找到相关的段落、对话或数据作为依据。
    2.  **常识融合**：**关键步骤！** 请调用你的外部知识库（常识、医学常识、社会运作逻辑、技术原理），对原文内容进行解读。
        - 例如：文中说"白细胞低"，你要结合常识指出这意味着"病毒感染，免疫系统受压制"。
        - 例如：文中说"找关系进医院"，你要结合常识指出这反映了"医疗资源挤兑下的社会资本博弈"。
    3.  **深度结论**：综合原文和常识，给出这个问题的深刻答案。
    
    请直接输出回答内容。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    answer = llm.invoke(messages).content
    
    # 记录这一轮的 Q&A
    qa_entry = f"❓ **Q**: {question}\n💡 **A**: {answer}"
    
    return {
        "qa_pairs": [qa_entry], # 累加到 state 中
        "next": "Planner"       # 回去 Planner 看看还需要问什么
    }

# === 3. Writer Node: 综合输出者 ===
# 改进点：能够处理通用长文，将碎片化的 Q&A 融合成连贯的深度报告
def writer_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    doc_title = state.get("doc_title", "文档")
    
    llm = get_llm()
    
    # 将 Planner 和 Researcher 辛苦几轮挖掘出来的"深度素材"拼接起来
    history_text = "\n\n".join(qa_history)
    
    task_prompt = f"""
    我们已经完成了对《{doc_title}》的深度阅读。
    
    【深度思考素材（Q&A 记录）】
    {history_text}
    
    【写作任务】
    请根据文档类型，利用上述素材，撰写一份**深度导读与分析报告**。
    
    请自适应选择以下结构之一：
    
    **模式 A：如果是【纪实/故事/社会新闻】**（如医疗经历、人物传记）
    1.  **核心冲突与背景**：用一句话概括故事的本质矛盾。
    2.  **关键决策复盘 (Timeline & Decisions)**：
        - 按时间线梳理关键节点。
        - **重点分析**：在哪些节点做错了？结合常识，正确的做法应该是什么？
    3.  **深层社会/人性洞察**：
        - 透过故事表象，看到了什么社会运作逻辑（如医疗资源、家庭关系）？
    4.  **警示与行动指南**：
        - 普通读者读完这篇长文，明天应该做什么改变？
    
    **模式 B：如果是【技术/学术/说明文】**
    1.  **核心理念 (The Big Idea)**：一句话解释它解决了什么问题。
    2.  **实现逻辑/架构拆解**：基于 Q&A 素材，解释其运作原理。
    3.  **优劣势深度辩证**：结合常识，分析它的局限性在哪里？
    4.  **应用场景**：到底该在什么情况下使用？
    
    【要求】
    - 标题自拟，具有吸引力。
    - 必须充分利用 Q&A 中的分析成果，不要忽略 Planner 的劳动。
    - 语气专业、客观、有深度。
    """
    
    messages = [
        SystemMessage(content=get_cached_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    report = llm.invoke(messages).content
    
    return {
        "final_report": report,
        "next": "Outlooker" # 依然保留 Outlooker 做最后的延伸
    }

# === 4. Outlooker Node: 最后的升华 ===
# 保持原有的逻辑，做扩展延伸，效果依然很好
def outlook_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    current_report = state["final_report"]
    
    llm = get_llm()
    
    task_prompt = f"""
    你是一个极其注重实用的咨询顾问。
    请阅读当前的分析报告，并增加一个 **# 🚀 扩展思考与资源** 章节。
    
    - 如果是故事/案例：推荐相关的书籍、电影或急救知识（如推荐《最好的告别》、心肺复苏指南）。
    - 如果是技术：推荐相关的 GitHub 库、替代方案对比。
    
    请直接输出 Markdown 内容追加到末尾。
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

# === 构建图 (保持不变) ===
def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("Planner", planner_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Writer", writer_node)
    workflow.add_node("Outlooker", outlook_node)

    workflow.set_entry_point("Planner")

    def route(state): return state["next"]

    workflow.add_conditional_edges(
        "Planner", route, 
        {"Researcher": "Researcher", "Writer": "Writer"}
    )
    
    workflow.add_edge("Researcher", "Planner")
    workflow.add_edge("Writer", "Outlooker")
    workflow.add_edge("Outlooker", END)
    
    return workflow.compile()

deep_graph = build_graph()