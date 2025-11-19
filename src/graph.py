"""LangGraph 图构建与编译。"""

from langgraph.graph import StateGraph, END
from src.state import AgentState
from src import nodes


def decide_route(state: AgentState) -> str:
    """路由决策逻辑。"""
    if state.get("search_needed"):
        # 限制重试次数为 3 次
        if state.get("search_count", 0) < 3:
            return "transform_query"
    return "generate"


# 构建图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("retrieve", nodes.retrieve)
workflow.add_node("grade_documents", nodes.grade_documents)
workflow.add_node("transform_query", nodes.transform_query)
workflow.add_node("generate", nodes.generate)

# 设置边
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")

workflow.add_conditional_edges(
    "grade_documents",
    decide_route,
    {
        "transform_query": "transform_query",
        "generate": "generate"
    }
)

workflow.add_edge("transform_query", "retrieve")
workflow.add_edge("generate", END)

# 编译图
graph = workflow.compile()