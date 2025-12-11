# src/nodes/ppt_nodes.py
import json
from langchain_core.messages import HumanMessage
from src.nodes.common import get_llm
from src.prompts import get_ppt_planner_prompt, get_ppt_writer_prompt
from src.state import PPTState
from src.utils.ppt_renderer import generate_ppt_file

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
    """渲染工：生成文件"""
    slides = state["final_ppt_content"]
    title = state.get("doc_title", "DeepSeek_Generated")
    
    try:
        # 清理非法字符作为文件名
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ','-','_')]).strip()
        file_path = generate_ppt_file(slides, filename=f"{safe_title}.pptx")
        return {
            "ppt_file_path": file_path,
            "run_logs": [f"✅ PPT 文件生成完毕: {file_path}"]
        }
    except Exception as e:
        return {"run_logs": [f"❌ 渲染失败: {e}"]}