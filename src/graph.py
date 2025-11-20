"""LangGraph 图构建与编译。"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
from src import nodes

# 定义条件路由逻辑
def route_supervisor(state: AgentState) -> str:
    # 读取 Supervisor 决定的 next 字段
    return state["next"]

workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("Supervisor", nodes.supervisor_node)
workflow.add_node("Searcher", nodes.search_node)
workflow.add_node("Answerer", nodes.answer_node)

# 设置入口
workflow.set_entry_point("Supervisor")

# 添加边
# 1. Supervisor -> (Searcher 或 Answerer)
workflow.add_conditional_edges(
    "Supervisor",
    route_supervisor,
    {
        "Searcher": "Searcher",
        "Answerer": "Answerer"
    }
)

# 2. Searcher -> Supervisor (搜完回去汇报)
workflow.add_edge("Searcher", "Supervisor")

# 3. Answerer -> END (回答完结束)
workflow.add_edge("Answerer", END)

graph = workflow.compile()