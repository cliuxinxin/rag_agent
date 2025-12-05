# src/graphs/deep_read_graph.py
from langgraph.graph import StateGraph, END
from src.state import AgentState
# 导入拆分后的节点
from src.nodes.read_nodes import planner_node, writer_node, researcher_node, outlook_node

def build_deep_read_graph():
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("Planner", planner_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Writer", writer_node)
    workflow.add_node("Outlooker", outlook_node)

    # 设置入口
    workflow.set_entry_point("Planner")

    # 定义边
    def route(state): return state["next"]

    workflow.add_conditional_edges(
        "Planner", route, 
        {"Researcher": "Researcher", "Writer": "Writer"}
    )
    
    workflow.add_edge("Researcher", "Planner")
    workflow.add_edge("Writer", "Outlooker")
    workflow.add_edge("Outlooker", END)
    
    return workflow.compile()

# 创建单例供外部调用
deep_read_graph = build_deep_read_graph()