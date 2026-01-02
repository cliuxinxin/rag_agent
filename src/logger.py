import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 创建日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def get_logger(name: str):
    """
    获取配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 防止重复添加 handler (Streamlit 重运行特性导致)
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.INFO)

    # 1. 格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 2. 文件处理器 (按大小轮转，最大 5MB，保留 5 个备份)
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", 
        maxBytes=5*1024*1024, 
        backupCount=5, 
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 3. 错误日志单独文件
    error_file_handler = RotatingFileHandler(
        LOG_DIR / "error.log", 
        maxBytes=5*1024*1024, 
        backupCount=5, 
        encoding='utf-8'
    )
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR)

    # 4. 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(error_file_handler)
    logger.addHandler(console_handler)

    return logger

