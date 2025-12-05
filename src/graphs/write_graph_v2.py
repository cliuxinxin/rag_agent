from langgraph.graph import StateGraph, END
from src.state import NewsroomState
from src.nodes.write_nodes_v2 import (
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
    wf.add_node("AngleGen", angle_generator_node)
    wf.add_node("OutlineGen", outline_architect_node)

    wf.set_entry_point("AngleGen")

    wf.add_edge("AngleGen", END)
    wf.add_edge("OutlineGen", END)

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

