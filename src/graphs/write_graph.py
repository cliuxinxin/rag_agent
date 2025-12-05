# src/graphs/write_graph.py
from langgraph.graph import StateGraph, END
from src.state import WriterState
from src.nodes.write_nodes import iterative_writer_node
# 注意：你需要把 plan_node, research_node 等也从 write_nodes 导出来
# 假设你已经把它们全放到了 src/nodes/write_nodes.py
from src.nodes.write_nodes import (
    plan_node, research_node, plan_check_node, 
    report_node, outline_node, 
    outline_refiner_node, social_summary_node
)

# ... 这里复制 write_flow.py 里 build_research_graph 等逻辑 ...
# 确保引用的是上面的 imports

def build_drafting_graph():
    wf = StateGraph(WriterState)
    wf.add_node("Writer", iterative_writer_node)
    wf.add_node("SocialSummary", social_summary_node)
    wf.set_entry_point("Writer")
    wf.add_edge("Writer", "SocialSummary")
    wf.add_edge("SocialSummary", END)
    return wf.compile()

# ... 定义其他 graph ...

drafting_graph = build_drafting_graph()
# 确保导出了 research_graph, drafting_graph, refine_graph