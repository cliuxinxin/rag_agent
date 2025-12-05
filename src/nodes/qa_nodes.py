# src/nodes/qa_nodes.py
import re
from langchain_core.messages import HumanMessage, SystemMessage
from src.nodes.common import get_llm
# 引用你提取的 prompts
from src.prompts import get_context_caching_system_prompt, get_qa_planner_prompt, get_qa_writer_prompt
from src.state import AgentState

# 复用 read_nodes 里的 researcher_node，或者在这里重新定义
from src.nodes.read_nodes import researcher_node

def qa_planner_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    user_goal = state["user_goal"]
    loop = state.get("loop_count", 0)
    MAX_LOOPS = 5
    
    llm = get_llm()
    history_text = "\n".join(qa_history) if qa_history else "（暂无，第一轮分析）"
    
    # 使用 Prompt
    task_prompt = get_qa_planner_prompt(loop, MAX_LOOPS, user_goal, history_text)
    
    messages = [
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    response = llm.invoke(messages).content.strip()
    question = response.replace('"', '').replace("'", "")
    
    if "TERMINATE" in response or loop >= MAX_LOOPS:
        return {"next": "QAWriter", "current_question": ""}
    else:
        return {
            "next": "Researcher", 
            "current_question": question, 
            "loop_count": loop + 1
        }

def qa_writer_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    qa_history = state.get("qa_pairs", [])
    doc_title = state.get("doc_title", "文档")
    user_goal = state["user_goal"]
    
    llm = get_llm()
    history_text = "\n\n".join(qa_history)
    
    # 使用 Prompt
    task_prompt = get_qa_writer_prompt(doc_title, user_goal, history_text)
    
    messages = [
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    answer = llm.invoke(messages).content
    
    return {
        "final_report": answer,
        "next": "Suggester"
    }

def suggester_node(state: AgentState) -> dict:
    full_text = state["full_content"]
    user_goal = state["user_goal"]
    current_answer = state["final_report"]
    
    llm = get_llm()
    
    task_prompt = f"""
    基于文档和对话，推荐 3 个值得用户继续追问的问题。
    用户问题：{user_goal}
    AI回答：{current_answer}
    格式：只输出3行文本，每行一个问题。
    """
    
    messages = [
        SystemMessage(content=get_context_caching_system_prompt(full_text)),
        HumanMessage(content=task_prompt)
    ]
    
    response = llm.invoke(messages).content.strip()
    
    lines = response.split('\n')
    clean_questions = []
    for line in lines:
        clean = re.sub(r"^[\d\.\-\•\s]+", "", line).strip()
        if clean:
            clean_questions.append(clean)
            
    return {
        "suggested_questions": clean_questions[:3],
        "next": "END"
    }