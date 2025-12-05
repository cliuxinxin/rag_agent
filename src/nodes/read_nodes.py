# src/nodes/read_nodes.py
from langchain_core.messages import HumanMessage, SystemMessage
from src.nodes.common import get_llm
from src.prompts import get_context_caching_system_prompt, get_read_planner_prompt, get_read_writer_prompt
from src.state import AgentState

def planner_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    loop = state.get("loop_count", 0)
    MAX_LOOPS = 4 
    
    llm = get_llm()
    history_text = "\n".join(qa_history) if qa_history else "（暂无，这是第一轮分析）"
    
    # 使用提取出来的 Prompt
    task_prompt = get_read_planner_prompt(loop, MAX_LOOPS, history_text)
    
    messages = [
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    response = llm.invoke(messages).content.strip()
    question = response.replace('"', '').replace("'", "")
    
    if "TERMINATE" in response or loop >= MAX_LOOPS:
        return {"next": "Writer", "current_question": ""}
    else:
        return {
            "next": "Researcher", 
            "current_question": question, 
            "loop_count": loop + 1
        }

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
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    answer = llm.invoke(messages).content
    
    # 记录这一轮的 Q&A
    qa_entry = f"❓ **Q**: {question}\n💡 **A**: {answer}"
    
    return {
        "qa_pairs": [qa_entry], # 累加到 state 中
        "next": "Planner"       # 回去 Planner 看看还需要问什么
    }

def writer_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    doc_title = state.get("doc_title", "文档")
    
    llm = get_llm()
    
    # 将 Planner 和 Researcher 辛苦几轮挖掘出来的"深度素材"拼接起来
    history_text = "\n\n".join(qa_history)
    
    task_prompt = get_read_writer_prompt(doc_title, history_text)
    
    messages = [
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    report = llm.invoke(messages).content
    
    return {
        "final_report": report,
        "next": "Outlooker" # 依然保留 Outlooker 做最后的延伸
    }

def outlook_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    current_report = state["final_report"]
    # 获取积累的所有问答对（思考过程）
    qa_history = state.get("qa_pairs", [])
    
    llm = get_llm()
    
    # 1. 生成 Outlook 内容 (保持原有逻辑)
    task_prompt = f"""
    你是一个极其注重实用的咨询顾问。
    请阅读当前的分析报告，并增加一个 **# 🚀 扩展思考与资源** 章节。
    
    - 如果是故事/案例：推荐相关的书籍、电影或急救知识。
    - 如果是技术：推荐相关的 GitHub 库、替代方案对比。
    
    请直接输出 Markdown 内容追加到末尾。
    """
    
    messages = [
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    outlook_content = llm.invoke(messages).content
    
    # 2. 拼接：原报告 + Outlook
    final_full_report = current_report + "\n\n" + outlook_content
    
    # === 3. 新增核心逻辑：将思考过程追加到文末 ===
    # 使用 HTML <details> 标签实现折叠效果，既保留了数据，又不影响阅读体验
    if qa_history:
        log_section = "\n\n---\n\n<details>\n<summary>🧠 点击查看 AI 完整思考与推演过程 (Trace Logs)</summary>\n\n"
        
        log_section += "> 以下记录了 Agent 从阅读到提问、再到结合常识推理的完整思维链。\n\n"
        
        for i, pair in enumerate(qa_history):
            # pair 的格式已经是 "❓ Q: ... \n💡 A: ..."
            # 我们稍微美化一下格式
            log_section += f"#### 🔄 第 {i+1} 轮思考\n"
            log_section += f"{pair}\n\n"
            
        log_section += "</details>\n"
        
        final_full_report += log_section
    
    return {
        "final_report": final_full_report,
        "next": "END"
    }