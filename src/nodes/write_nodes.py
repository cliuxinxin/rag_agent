# src/nodes/write_nodes.py
from langchain_core.messages import HumanMessage, SystemMessage
from src.nodes.common import get_llm
from src.prompts import get_context_caching_system_prompt, get_writer_iteration_prompt
from src.state import WriterState

def iterative_writer_node(state: WriterState) -> dict:
    full_text = state["full_content"] # 核心：原文缓存
    report = state["research_report"]
    outline = state["current_outline"]
    idx = state["current_section_index"]
    previous_context = state.get("full_draft", "") # 已生成的正文
    
    if idx < 0 or idx >= len(outline):
        return {"current_section_content": "", "next": "END"}
    
    target_section = outline[idx]
    llm = get_llm()
    
    # 构造 System Prompt (复用 Context Caching)
    system_msg = SystemMessage(content=get_context_caching_system_prompt(full_text))
    
    # === 修改点：增强 Prompt 约束 ===
    prompt = get_writer_iteration_prompt(idx, target_section['title'], report, target_section['desc'], previous_context)
    
    content = llm.invoke([system_msg, HumanMessage(content=prompt)]).content
    
    # === 新增：简单的后处理清洗 ===
    # 防止 AI 还是不听话，输出了标题，这里做一个简单的字符串剔除
    clean_content = content.strip()
    # 如果开头就是标题，去掉它
    if clean_content.startswith(target_section['title']):
        clean_content = clean_content[len(target_section['title']):].strip()
    # 去掉可能存在的 Markdown 标题标记 (e.g. ## Title)
    import re
    clean_content = re.sub(r'^#+\s*' + re.escape(target_section['title']) + r'\s*\n', '', clean_content, flags=re.IGNORECASE).strip()

    return {"current_section_content": clean_content, "next": "END"}