from langgraph.graph import StateGraph, END
from src.state import DeepWriteState
from src.nodes.write_nodes_v3 import (
    angle_proposer_node,     # [新增]
    structure_gen_node,      # [新增] 合并了 TitleGen, Analyst, Architect
    topic_generator_node,
    analyst_node,
    architect_node,
    writer_node,
    reviewer_node,
    polisher_node,
    check_continue,          # [新增]
    fast_finish_node         # [新增]
)

# 路由条件函数
def check_continue(state: DeepWriteState):
    """路由条件：决定是否继续写作或进入评审"""
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

def build_graph():
    wf = StateGraph(DeepWriteState)
    
    # 注册所有节点
    wf.add_node("AngleProposer", angle_proposer_node)     # [新增] 第一步：选方向
    wf.add_node("StructureGen", structure_gen_node)       # [新增] 第二步：生成标题和大纲（合并）
    wf.add_node("TopicGen", topic_generator_node)         # [保留] 兼容旧流程
    wf.add_node("Analyst", analyst_node)
    wf.add_node("Architect", architect_node)
    wf.add_node("Writer", writer_node)
    wf.add_node("Reviewer", reviewer_node)
    wf.add_node("Polisher", polisher_node)
    wf.add_node("FastFinish", fast_finish_node)
    
    # === 新版流程 (使用 AngleProposer + StructureGen) ===
    # 这里保持图的完整性，但实际由 API 路由层控制哪个节点开始运行
    wf.set_entry_point("AngleProposer")  # 默认入口
    
    # AngleProposer -> END (暂停点，等待用户选择)
    wf.add_edge("AngleProposer", END)
    
    # 当前端提交选择后，应该直接调用 StructureGen
    # 为了兼容，我们还是连接起来，但 API 层可以控制从哪里开始
    wf.add_edge("StructureGen", "Writer")
    
    # === 旧版流程 (TopicGen -> Analyst -> Architect) ===
    # 这是为了兼容旧版本，新版本会跳过这个
    wf.add_edge("TopicGen", "Analyst")
    wf.add_edge("Analyst", "Architect")
    wf.add_edge("Architect", "Writer")
    
    # === 写作循环 ===
    wf.add_conditional_edges(
        "Writer",
        check_continue,
        {
            "Writer": "Writer",      # 继续写下一章
            "Reviewer": "Reviewer",  # 进入审阅
            "FastFinish": "FastFinish" # 极速模式，直接完成
        }
    )
    
    # === 审阅和润色流程 ===
    wf.add_edge("Reviewer", "Polisher")
    wf.add_edge("Polisher", END)
    wf.add_edge("FastFinish", END)
    
    return wf.compile()

write_graph_v3 = build_graph()