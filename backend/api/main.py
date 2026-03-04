"""
RAG Agent API - FastAPI 主入口
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 导入路由模块
from api.routes import chat_routes, db_routes, read_routes, ppt_routes

# 创建 FastAPI 应用
app = FastAPI(
    title="RAG Agent API",
    description="基于 LangGraph 和 DeepSeek 的 RAG 系统 API",
    version="1.0.0"
)

# CORS 配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Vite 开发服务器
        "http://localhost:80",         # Nginx 生产环境
        "http://127.0.0.1:5173",
        "http://127.0.0.1:80"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    print(f"[{request.method}] {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    return response

# 注册路由
app.include_router(chat_routes.router, prefix="/api/chat", tags=["聊天"])
app.include_router(db_routes.router, prefix="/api/db", tags=["数据库"])
app.include_router(read_routes.router, prefix="/api/read", tags=["深度阅读"])
app.include_router(ppt_routes.router, prefix="/api/ppt", tags=["PPT 生成"])

# 健康检查接口
@app.get("/health", summary="健康检查")
async def health_check():
    """检查服务是否正常运行"""
    return {
        "status": "ok",
        "timestamp": time.time(),
        "version": "1.0.0"
    }

# 根路径
@app.get("/", summary="API 信息")
async def root():
    """API 欢迎页面"""
    return {
        "message": "Welcome to RAG Agent API",
        "docs": "/docs",  # Swagger UI
        "redoc": "/redoc"  # ReDoc
    }

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行的初始化"""
    print("=" * 60)
    print("🚀 RAG Agent API 启动成功!")
    print("📌 API 文档：http://localhost:8000/docs")
    print("📌 ReDoc: http://localhost:8000/redoc")
    print("=" * 60)

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理工作"""
    print("👋 RAG Agent API 已关闭")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
