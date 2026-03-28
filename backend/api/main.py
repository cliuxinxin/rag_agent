"""
RAG Agent API - FastAPI 主入口
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time
import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

# 导入路由模块
from api.routes import chat_routes, db_routes, read_routes, ppt_routes, kb_routes, write_routes, log_routes, mastery_routes, skill_routes, auth_routes, qa_routes, write_v3_routes, copilot_routes
# 数据库初始化
from src.db import init_db
from fastapi.staticfiles import StaticFiles

# 创建 FastAPI 应用
app = FastAPI(
    title="RAG Agent API",
    description="基于 LangGraph 和 DeepSeek 的 RAG 系统 API",
    version="1.0.0"
)

# 挂载静态资源目录 (用于 Skill Agent 生成的图表等)
skills_static_path = os.path.join(project_root, 'skills')
if not os.path.exists(skills_static_path):
    os.makedirs(skills_static_path)
app.mount("/static/skills", StaticFiles(directory=skills_static_path), name="skills")

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
app.include_router(kb_routes.router, prefix="/api/kb", tags=["知识库"])
app.include_router(write_routes.router, prefix="/api/write", tags=["深度写作"])
app.include_router(log_routes.router, prefix="/api/log", tags=["日志系统"])
app.include_router(mastery_routes.router, prefix="/api/mastery", tags=["深度掌握"])
app.include_router(skill_routes.router, prefix="/api/skill", tags=["技能智能体"])
app.include_router(auth_routes.router, prefix="/api/auth", tags=["用户认证"])
app.include_router(qa_routes.router, prefix="/api/qa", tags=["深度追问"])
app.include_router(write_v3_routes.router, prefix="/api/write/v3", tags=["DeepWrite V3"])
app.include_router(copilot_routes.router, prefix="/api/copilot", tags=["长文伴读"])

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
    print("🚀 RAG Agent API 启动中...")

    # 初始化数据库（幂等）
    try:
        print("🔨 正在检查/初始化数据库...")
        init_db()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

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
    # === [核心修复] 增加超时参数 ===
    # --timeout-keep-alive 600: 保持连接 10 分钟，匹配 Nginx 配置
    # --workers 1: 云服务器通常 CPU 只有 1-2 核，强制设为 1 个 worker 避免抢占资源导致死锁
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        timeout_keep_alive=600,
        workers=1
    )
