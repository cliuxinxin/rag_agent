# src/nodes/common.py
import os
from langchain_openai import ChatOpenAI

# === [修改] 适配 Langfuse v3 导入路径 (带兼容性保护) ===
try:
    # v3 新路径
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:
    try:
        # v2 旧路径 (以防万一)
        from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
    except ImportError:
        LangfuseCallbackHandler = None

def get_llm():
    # === [修改] 初始化回调 ===
    callbacks = []
    if LangfuseCallbackHandler:
        try:
            # v3 初始化不需要传参，自动读取环境变量
            langfuse_handler = LangfuseCallbackHandler()
            callbacks.append(langfuse_handler)
        except Exception as e:
            print(f"Langfuse init warning: {e}")

    return ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        temperature=0.3,
        max_retries=2,
        max_tokens=8000,
        callbacks=callbacks 
    )