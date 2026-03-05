from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import os
from pathlib import Path
from src.logger import LOG_DIR

router = APIRouter()

def tail_file(file_path: Path, n: int = 100) -> List[str]:
    """读取文件最后 n 行"""
    if not file_path.exists():
        return []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # 简单实现：读取所有行取最后 n 行
            # 对于 5MB 的日志文件，这种方式性能是可以接受的
            lines = f.readlines()
            return lines[-n:]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")

@router.get("/app")
async def get_app_logs(n: int = Query(100, ge=1, le=1000)):
    """获取 app.log 的最后 n 行"""
    log_path = LOG_DIR / "app.log"
    return {"logs": tail_file(log_path, n)}

@router.get("/error")
async def get_error_logs(n: int = Query(100, ge=1, le=1000)):
    """获取 error.log 的最后 n 行"""
    log_path = LOG_DIR / "error.log"
    return {"logs": tail_file(log_path, n)}

@router.get("/list")
async def list_logs():
    """列出所有日志文件"""
    if not LOG_DIR.exists():
        return {"files": []}
    
    files = []
    for f in LOG_DIR.glob("*.log*"):
        stats = f.stat()
        files.append({
            "name": f.name,
            "size": stats.st_size,
            "mtime": stats.st_mtime
        })
    return {"files": sorted(files, key=lambda x: x["mtime"], reverse=True)}
