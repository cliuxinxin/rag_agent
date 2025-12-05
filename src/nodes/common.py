# src/nodes/common.py
import os
from langchain_openai import ChatOpenAI

def get_llm():
    return ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        temperature=0.3,
        max_retries=2,
        # 显式拉大输出上限以防止截断
        # DeepSeek V3 最大支持 8192 output tokens
        max_tokens=8000
    )