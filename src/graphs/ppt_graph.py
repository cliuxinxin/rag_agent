# src/graphs/ppt_graph.py
from langgraph.graph import StateGraph, END
from src.state import PPTState
from src.nodes.ppt_nodes import ppt_planner_node, ppt_writer_node, ppt_renderer_node

def build_ppt_graph():
    wf = StateGraph(PPTState)
    
    wf.add_node("Planner", ppt_planner_node)
    wf.add_node("Writer", ppt_writer_node)
    wf.add_node("Renderer", ppt_renderer_node)
    
    wf.set_entry_point("Planner")
    
    wf.add_edge("Planner", "Writer")
    wf.add_edge("Writer", "Renderer")
    wf.add_edge("Renderer", END)
    
    return wf.compile()

ppt_graph = build_ppt_graph()