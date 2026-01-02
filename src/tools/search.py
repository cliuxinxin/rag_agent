import os
import requests
from src.logger import get_logger

logger = get_logger("Tool_Search")

def tavily_search(query: str, max_results: int = 3) -> str:
    """
    执行 Tavily 搜索并返回格式化的文本结果。
    """
    logger.info(f"执行搜索: '{query}'")
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY 未设置，跳过搜索。")
        return ""

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",  # 深度搜索，适合写长文
        "include_answer": True,
        "max_results": max_results
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        results_text = []
        
        # 1. Tavily 智能摘要
        if data.get("answer"):
            results_text.append(f"【Tavily 智能摘要】: {data['answer']}")
            
        # 2. 网页片段
        for res in data.get("results", []):
            title = res.get("title", "No Title")
            content = res.get("content", "")
            url = res.get("url", "")
            results_text.append(f"【来源: {title}】\nURL: {url}\n内容: {content}\n")
        
        result_count = len(data.get("results", []))
        logger.info(f"搜索成功，找到 {result_count} 条结果")
        return "\n\n".join(results_text)
        
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {e}", exc_info=True)
        return ""