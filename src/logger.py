import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 定义日志格式
# [时间] [级别] [模块] [TraceID] 信息
FORMAT_STR = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加 Handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(FORMAT_STR, datefmt='%Y-%m-%d %H:%M:%S')

    # 1. 控制台输出 (方便 Docker logs 查看)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. 文件输出 (App.log) - 记录所有信息
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5, 
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# 创建一个专门用于记录 Prompt 的 logger
trace_logger = logging.getLogger("LLM_Trace")
trace_logger.setLevel(logging.INFO)
# 防止向上传播到 root logger，避免重复输出
trace_logger.propagate = False

# 检查是否已经有 handler，避免重复添加
if not trace_logger.handlers:
    trace_handler = RotatingFileHandler(
        LOG_DIR / "llm_trace.log",
        maxBytes=20*1024*1024, # 20MB
        backupCount=3,
        encoding='utf-8'
    )
    trace_handler.setFormatter(logging.Formatter('%(asctime)s\n%(message)s\n' + '-'*80 + '\n'))
    trace_logger.addHandler(trace_handler)

def log_llm_trace(stage: str, prompt: str, response: str, duration: float):
    """记录详细的 LLM 调用链路"""
    msg = f"""【Stage】: {stage}
【Time】: {duration:.2f}s
【Prompt Preview】:
{prompt[:1000]} ... (length: {len(prompt)})
【Response Preview】:
{response[:1000]} ... (length: {len(response)})
"""
    trace_logger.info(msg)