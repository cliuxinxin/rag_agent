# RAG Agent Backend API

基于 FastAPI 的 RAG Agent 后端服务，提供流式对话、知识库管理等功能。

## 🚀 快速启动

### 方式一：使用启动脚本（推荐）

```bash
cd backend
python start_server.py
```

### 方式二：使用 Uvicorn 命令

```bash
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 API 文档

启动后访问以下地址查看交互式 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 安装依赖

```bash
pip install -r requirements.txt
```

## 📁 目录结构

```
backend/
├── api/
│   ├── main.py              # FastAPI 应用入口
│   ├── routes/
│   │   ├── chat_routes.py   # 聊天相关接口
│   │   └── db_routes.py     # 数据库相关接口
│   └── __init__.py
├── src/                     # 原有核心逻辑 (符号链接或复制)
├── storage/                 # 数据存储 (SQLite, FAISS)
├── requirements.txt         # Python 依赖
└── start_server.py          # 启动脚本
```

## 🎯 核心接口

### 1. 流式聊天接口

```bash
POST /api/chat/stream
Content-Type: application/json

{
    "query": "你的问题",
    "session_id": "会话 ID",
    "kb_ids": [1, 2, 3],
    "mode": "chat"
}
```

响应为 SSE (Server-Sent Events) 流格式。

### 2. 获取会话列表

```bash
GET /api/db/sessions
```

### 3. 获取会话消息

```bash
GET /api/db/sessions/{session_id}/messages
```

### 4. 创建会话

```bash
POST /api/db/sessions?title=新会话&mode=chat
```

## 🧪 测试示例

使用 curl 测试流式接口：

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "你好", "session_id": "test_001"}'
```

## 🐳 Docker 部署

构建并运行：

```bash
docker build -f Dockerfile.backend -t rag_backend .
docker run -p 8000:8000 -v $(pwd)/storage:/app/storage rag_backend
```

或使用 docker-compose：

```bash
docker-compose up -d
```

## 📝 开发注意事项

1. **路径配置**: 所有路由文件都需要添加项目根目录到 `sys.path`
2. **SSE 缓冲**: 确保禁用 Nginx 缓冲以支持实时流式传输
3. **CORS**: 已配置允许前端跨域访问
4. **日志**: 请求日志通过中间件自动记录

## 🔐 环境变量

从 `.env` 文件读取配置：

- `DEEPSEEK_API_KEY`: DeepSeek API 密钥
- `OPENAI_API_KEY`: OpenAI API 密钥 (可选)
- 其他配置参考原项目

## 📊 性能优化

- 启用 Uvicorn 的 worker 模式处理并发
- 使用异步 I/O 提升吞吐量
- SSE 连接保持长连接，减少握手开销

## 🛠️ 待扩展功能

- [ ] JWT 认证
- [ ] WebSocket 支持
- [ ] 文件上传接口
- [ ] PPT 生成接口
- [ ] 知识库管理接口
- [ ] 用户权限管理
