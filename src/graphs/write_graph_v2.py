from langgraph.graph import StateGraph, END
from src.state import NewsroomState
from src.nodes.write_nodes_v2 import (
    macro_search_node, # <--- [新增]
    angle_generator_node,
    outline_architect_node,
    internal_researcher_node,
    section_drafter_node,
    dispatcher_node,
    reviewer_node,
    polisher_node
)


# === 图 1: 策划与架构 (Planning Workflow) ===
def build_planning_graph():
    wf = StateGraph(NewsroomState)
    
    # 注册节点
    wf.add_node("MacroSearch", macro_search_node)
    wf.add_node("AngleGen", angle_generator_node)
    # 注意：OutlineGen 虽然注册了，但在 UI 中是单独调用的，或者这里不需要连上
    # 如果想保持代码整洁，可以先不注册 OutlineGen，或者注册了但不连线
    # wf.add_node("OutlineGen", outline_architect_node) 

    # 设置入口
    wf.set_entry_point("MacroSearch")

    # === [关键修复] ===
    # 原来的错误连线： MacroSearch -> AngleGen -> OutlineGen -> END
    # 正确的连线：    MacroSearch -> AngleGen -> END
    
    wf.add_edge("MacroSearch", "AngleGen") 
    wf.add_edge("AngleGen", END)  # <--- 修改这里，让它在这里停下！

    return wf.compile()


# === 图 2: 写作流水线 (Drafting Workflow) ===
def build_drafting_graph():
    wf = StateGraph(NewsroomState)

    wf.add_node("Dispatcher", dispatcher_node)
    wf.add_node("Researcher", internal_researcher_node)
    wf.add_node("Drafter", section_drafter_node)
    wf.add_node("Reviewer", reviewer_node)
    wf.add_node("Polisher", polisher_node)

    wf.set_entry_point("Dispatcher")

    wf.add_conditional_edges(
        "Dispatcher",
        lambda x: x["next"],
        {
            "Researcher": "Researcher",
            "Reviewer": "Reviewer"
        }
    )

    wf.add_edge("Researcher", "Drafter")
    wf.add_edge("Drafter", "Dispatcher")
    wf.add_edge("Reviewer", "Polisher")
    wf.add_edge("Polisher", END)

    return wf.compile()


planning_graph = build_planning_graph()
drafting_graph = build_drafting_graph()

