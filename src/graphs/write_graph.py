# src/graphs/write_graph.py
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes.write_nodes import (
    plan_node, research_node, plan_check_node, 
    report_node, outline_node, 
    iterative_writer_node, social_summary_node,
    outline_refiner_node
)

def build_research_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Planner", plan_node)
    wf.add_node("Researcher", research_node)
    wf.add_node("PlanCheck", plan_check_node)
    wf.add_node("ReportGenerator", report_node)
    wf.add_node("Outliner", outline_node)
    
    wf.set_entry_point("Planner")
    wf.add_edge("Planner", "Researcher")
    wf.add_edge("Researcher", "PlanCheck")
    wf.add_conditional_edges("PlanCheck", lambda x: x["next"], {"Planner": "Planner", "ReportGenerator": "ReportGenerator"})
    wf.add_edge("ReportGenerator", "Outliner")
    wf.add_edge("Outliner", END)
    return wf.compile()

def build_drafting_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Writer", iterative_writer_node)
    wf.add_node("SocialSummary", social_summary_node)
    wf.set_entry_point("Writer")
    wf.add_edge("Writer", "SocialSummary")
    wf.add_edge("SocialSummary", END)
    return wf.compile()

def build_refine_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Refiner", outline_refiner_node)
    wf.set_entry_point("Refiner")
    wf.add_edge("Refiner", END)
    return wf.compile()

research_graph = build_research_graph()
drafting_graph = build_drafting_graph()
refine_graph = build_refine_graph()