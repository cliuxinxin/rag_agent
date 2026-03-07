from langgraph.graph import StateGraph, END
from src.state import DeepWriteState
from src.nodes.write_nodes_v3 import (
    topic_generator_node, # 新增
    analyst_node,
    architect_node,
    writer_node,
    reviewer_node,
    polisher_node
)

# 路由条件函数
def check_continue(state: DeepWriteState):
    idx = state["current_section_index"]
    outline = state["outline"]
    
    if idx < len(outline):
        return "Writer" # 继续写下一章
    else:
        # 判断是否是极速模式
        if state.get("fast_mode", False):
            return "FastFinish"
        else:
            return "Reviewer" # 写完了，去审阅

# 极速模式下的快速收尾节点
async def fast_finish_node(state: DeepWriteState) -> dict:
    full_draft = "\n\n".join(state["section_drafts"])
    # 保存到数据库
    if state.get("project_id"):
        from src.db import update_project_draft, update_project_outline
        update_project_draft(state["project_id"], full_draft)
        if state.get("outline"):
            update_project_outline(state["project_id"], state["outline"])
    return {
        "final_article": full_draft,
        "run_logs": ["⚡ [极速模式] 跳过审阅，直接归档"]
    }

def build_graph():
    wf = StateGraph(DeepWriteState)
    
    # 注册节点
    wf.add_node("TopicGen", topic_generator_node) # 新增
    wf.add_node("Analyst", analyst_node)
    wf.add_node("Architect", architect_node)
    wf.add_node("Writer", writer_node)
    wf.add_node("Reviewer", reviewer_node)
    wf.add_node("Polisher", polisher_node)
    wf.add_node("FastFinish", fast_finish_node)
    
    # 设置入口：从生成主题开始
    wf.set_entry_point("TopicGen")
    
    # 连线
    wf.add_edge("TopicGen", "Analyst") # TopicGen -> Analyst
    wf.add_edge("Analyst", "Architect")
    wf.add_edge("Architect", "Writer")
    
    # 循环逻辑：Writer -> Check -> Writer/Reviewer/FastFinish
    wf.add_conditional_edges(
        "Writer",
        check_continue,
        {
            "Writer": "Writer",
            "Reviewer": "Reviewer",
            "FastFinish": "FastFinish"
        }
    )
    
    wf.add_edge("Reviewer", "Polisher")
    wf.add_edge("Polisher", END)
    wf.add_edge("FastFinish", END)
    
    return wf.compile()

write_graph_v3 = build_graph()