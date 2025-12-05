# src/graphs/deep_qa_graph.py
from langgraph.graph import StateGraph, END
from src.state import AgentState
# 引用拆分后的 qa_nodes
from src.nodes.qa_nodes import qa_planner_node, qa_writer_node, suggester_node, researcher_node

def build_deep_qa_graph():
    qa_workflow = StateGraph(AgentState)

    qa_workflow.add_node("QAPlanner", qa_planner_node)
    qa_workflow.add_node("Researcher", researcher_node)
    qa_workflow.add_node("QAWriter", qa_writer_node)
    qa_workflow.add_node("Suggester", suggester_node)

    qa_workflow.set_entry_point("QAPlanner")

    qa_workflow.add_conditional_edges(
        "QAPlanner", 
        lambda x: x["next"], 
        {"Researcher": "Researcher", "QAWriter": "QAWriter"}
    )

    qa_workflow.add_edge("Researcher", "QAPlanner")
    qa_workflow.add_edge("QAWriter", "Suggester")
    qa_workflow.add_edge("Suggester", END)

    return qa_workflow.compile()

deep_qa_graph = build_deep_qa_graph()