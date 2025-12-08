import os
import requests

def tavily_search(query: str, max_results: int = 3) -> str:
    """
    执行 Tavily 搜索并返回格式化的文本结果。
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("⚠️ Warning: TAVILY_API_KEY not found in env.")
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
            
        return "\n\n".join(results_text)
        
    except Exception as e:
        print(f"❌ Tavily Search Error: {e}")
        return ""