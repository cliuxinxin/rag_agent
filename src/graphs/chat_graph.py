# src/graphs/chat_graph.py
from langgraph.graph import StateGraph, END
from src.state import AgentState
# 引用新拆分的 chat_nodes
from src.nodes.chat_nodes import supervisor_node, search_node, answer_node

def route_supervisor(state: AgentState) -> str:
    return state["next"]

workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Searcher", search_node)
workflow.add_node("Answerer", answer_node)

workflow.set_entry_point("Supervisor")

workflow.add_conditional_edges(
    "Supervisor",
    route_supervisor,
    {"Searcher": "Searcher", "Answerer": "Answerer"}
)

workflow.add_edge("Searcher", "Supervisor")
workflow.add_edge("Answerer", END)

# 导出 graph 实例
chat_graph = workflow.compile()