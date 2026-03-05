#!/usr/bin/env python3
"""
FastAPI 后端启动脚本
用于开发和测试环境快速启动服务
"""
import uvicorn
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 也添加父目录（项目根目录）到路径
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def main():
    """启动 FastAPI 服务器"""
    print("=" * 60)
    print("🚀 启动 RAG Agent API 服务器")
    print("=" * 60)
    print()
    print("📌 API 文档地址:")
    print("   - Swagger UI: http://localhost:8000/docs")
    print("   - ReDoc: http://localhost:8000/redoc")
    print()
    print("🔧 按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()
    
    # 启动服务器
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式：自动重载
        log_level="info"
    )


if __name__ == "__main__":
    main()
