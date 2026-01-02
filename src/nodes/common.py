# src/nodes/common.py
import os
from langchain_openai import ChatOpenAI
from src.logger import get_logger

logger = get_logger("LLM_Factory")

def get_llm():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com")
    
    if not api_key:
        logger.critical("未检测到 DEEPSEEK_API_KEY 环境变量！")
    
    try:
        llm = ChatOpenAI(
            model="deepseek-chat",
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.3,
            max_retries=2,
            # 显式拉大输出上限以防止截断
            # DeepSeek V3 最大支持 8192 output tokens
            max_tokens=8000
        )
        # 此时还没有真正调用 API，但在调用 invoke 时如果出错，langchain 会抛出异常
        # 可以在这里记录一次 debug 日志
        logger.debug(f"LLM 实例已创建: {base_url}")
        return llm
    except Exception as e:
        logger.error(f"LLM 初始化失败: {e}", exc_info=True)
        raise e