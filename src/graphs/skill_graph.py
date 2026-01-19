# src/graphs/skill_graph.py
import sqlite3
from typing import Annotated, List, Literal, TypedDict, Optional
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

from src.nodes.common import get_llm # [修改] 复用通用 LLM
from src.logger import get_logger
from src.skills.loader import SkillRegistry
from src.skills.tools import DEFAULT_TOOLS, set_active_path

logger = get_logger("Skill_Graph")
registry = SkillRegistry()

# 数据库路径 (独立于主 DB，用于 Graph Memory)
SKILL_DB_PATH = Path("storage/skill_memory.sqlite")
SKILL_DB_PATH.parent.mkdir(exist_ok=True)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    active_skill: Optional[str]
    router_reasoning: Optional[str]

def router_node(state: AgentState):
    logger.info("--- 🚦 Node: Router ---")
    messages = state["messages"]
    
    registry.refresh()
    skills = registry.list_skills()
    
    # 获取 LLM
    llm = get_llm()

    if not isinstance(messages[-1], HumanMessage) or not skills:
        return {"active_skill": None}

    skill_list_str = "\n".join([f"- {s['name']}: {s['description']}" for s in skills])
    user_input = messages[-1].content
    current_skill = state.get("active_skill")

    prompt = f"""
    Role: Expert Skill Router
    
    You have a set of specialist agents (Skills) available:
    {skill_list_str}
    
    Current Active Skill: {current_skill if current_skill else "None"}
    User Request: "{user_input}"
    
    TASK: Decide which skill to activate.
    
    IMPORTANT RULES:
    1. If user explicitly mentions a skill, SWITCH to it.
    2. If current skill CANNOT handle request, SWITCH.
    3. Output ONLY the skill name or "default".
    """
    
    # 简单的调用，不需要复杂的 parser
    response = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    
    target = response if registry.get_skill(response) else None
    
    return {
        "active_skill": target,
        "router_reasoning": f"Routed to: {target}"
    }

def agent_node(state: AgentState):
    logger.info("--- 🤖 Node: Agent ---")
    skill_name = state.get("active_skill")
    skill = registry.get_skill(skill_name)
    
    system_text = "You are a helpful AI assistant."
    if skill:
        # [关键] 设置当前工具运行路径
        set_active_path(skill.root_path)
        
        system_text += f"\n\n=== ACTIVE SKILL: {skill.name} ===\n{skill.instructions}"
        
        # --- [新增优化] 自动列出可用脚本 ---
        scripts_dir = skill.root_path / "scripts"
        if scripts_dir.exists():
            scripts = [f.name for f in scripts_dir.glob("*.py")]
            if scripts:
                system_text += "\n\n=== AVAILABLE SCRIPTS (Executable) ===\n"
                system_text += "You can use the `run_skill_script` tool with the following files:\n"
                for s in scripts:
                    system_text += f"- {s}\n"
        # --------------------------------
        
        # 原有的 references 逻辑
        ref_dir = skill.root_path / "references"
        if ref_dir.exists():
            files = [f.name for f in ref_dir.glob("*") if f.is_file()]
            if files:
                system_text += "\n=== AVAILABLE REFERENCES (Docs) ===\n" + "\n".join([f"- {f}" for f in files])
    else:
        set_active_path(None)

    llm = get_llm()
    # 绑定工具
    model = llm.bind_tools(DEFAULT_TOOLS)
    
    full_messages = [SystemMessage(content=system_text)] + state["messages"]
    response = model.invoke(full_messages)
    
    return {"messages": [response]}

def tool_router(state: AgentState) -> Literal["tools", "end"]:
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:
        return "tools"
    return "end"

def build_skill_graph():
    # 使用独立的 SQLite 存储 Graph 状态，避免与主 DB 冲突
    conn = sqlite3.connect(str(SKILL_DB_PATH), check_same_thread=False)
    memory = SqliteSaver(conn)
    
    workflow = StateGraph(AgentState)
    workflow.add_node("router", router_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(DEFAULT_TOOLS))
    
    workflow.set_entry_point("router")
    workflow.add_edge("router", "agent")
    workflow.add_conditional_edges("agent", tool_router, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile(checkpointer=memory)

# 单例
skill_graph = build_skill_graph()