# src/nodes/ppt_nodes.py
import json
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.prompts import get_ppt_planner_prompt, get_ppt_writer_prompt
from src.state import PPTState
# 引用新函数
from src.ppt_renderer import generate_ppt_binary 

def ppt_planner_node(state: PPTState) -> dict:
    """策划师：生成大纲"""
    content = state["full_content"]
    count = state.get("slides_count", 10)
    llm = get_llm()
    
    msg = HumanMessage(content=get_ppt_planner_prompt(content, count))
    response = llm.invoke([msg]).content
    
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        outline = data.get("slides", [])
    except:
        # Fallback
        outline = [{"id": 1, "type": "cover", "title": "解析失败，请重试"}]
        
    return {
        "ppt_outline": outline, 
        "run_logs": ["✅ 策划师已完成 PPT 结构设计"]
    }

def ppt_writer_node(state: PPTState) -> dict:
    """撰稿人：填充内容"""
    content = state["full_content"]
    outline = state["ppt_outline"]
    llm = get_llm()
    
    # 把大纲转成字符串给 LLM 参考
    outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
    
    msg = HumanMessage(content=get_ppt_writer_prompt(content, outline_str))
    response = llm.invoke([msg]).content
    
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        final_content = json.loads(clean_json)
    except Exception as e:
        print(f"JSON Error: {e}")
        final_content = []

    return {
        "final_ppt_content": final_content,
        "run_logs": ["✅ 撰稿人已完成内容填充，准备渲染..."]
    }

def ppt_renderer_node(state: PPTState) -> dict:
    """渲染工：生成二进制流"""
    slides = state["final_ppt_content"]
    
    try:
        # 直接获取二进制数据
        ppt_bytes = generate_ppt_binary(slides)
        
        return {
            "ppt_binary": ppt_bytes, # 存入 State
            "run_logs": ["✅ PPT 渲染完成 (内存生成)"]
        }
    except Exception as e:
        return {"run_logs": [f"❌ 渲染失败: {e}"]}