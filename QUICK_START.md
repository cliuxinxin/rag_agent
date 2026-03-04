# 🚀 快速开始 - FastAPI 后端迁移

本指南帮助你快速完成从 Streamlit 到 FastAPI 的后端迁移，并测试核心功能。

---

## ✅ 第一阶段完成清单

- [x] 创建 FastAPI 项目结构 (`backend/`)
- [x] 实现聊天流式接口 (`/api/chat/stream`)
- [x] 实现数据库 CRUD 接口 (`/api/db/*`)
- [x] 配置 CORS 跨域支持
- [x] 添加请求日志中间件
- [x] 创建启动脚本和测试工具

---

## 📦 步骤 1: 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

**或者使用 pipenv/poetry:**

```bash
# 如果使用 pipenv
pipenv install -r requirements.txt
pipenv shell

# 如果使用 poetry
poetry install
poetry shell
```

---

## 🏃 步骤 2: 启动后端服务

### 方式一：使用启动脚本（推荐）

```bash
cd backend
python start_server.py
```

### 方式二：直接使用 uvicorn

```bash
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**成功标志:**

```
============================================================
🚀 RAG Agent API 启动成功!
📌 API 文档：http://localhost:8000/docs
📌 ReDoc: http://localhost:8000/redoc
============================================================
```

---

## 🔐 登录信息

系统默认启用了 JWT 认证，默认管理员账号如下：

- **用户名**: `admin`
- **密码**: `admin123`

> **提示**: 你可以通过设置环境变量 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 来修改默认凭据。

---

## 🧪 步骤 3: 测试 API 接口

### 方式一：使用测试脚本（推荐）

```bash
cd backend
./test_api.sh
```

**如果没有 jq 工具:**

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Windows (Git Bash)
choco install jq
```

### 方式二：手动 curl 测试

```bash
# 1. 健康检查
curl http://localhost:8000/health

# 2. 创建会话
curl -X POST "http://localhost:8000/api/db/sessions?title=测试&mode=chat"

# 3. 获取会话列表
curl http://localhost:8000/api/db/sessions

# 4. 流式聊天测试
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "你好", "session_id": "default"}'
```

### 方式三：Swagger UI 测试

浏览器访问：**http://localhost:8000/docs**

在 Swagger UI 中:
1. 展开 `/api/chat/stream` 接口
2. 点击 "Try it out"
3. 填写请求体:
   ```json
   {
     "query": "你好，请介绍一下你自己",
     "session_id": "test_001"
   }
   ```
4. 点击 "Execute"
5. 查看 SSE 流式响应

---

## 📊 步骤 4: 验证核心功能

### 测试 SSE 流式传输

创建一个简单的 Python 客户端测试：

```python
import requests

url = "http://localhost:8000/api/chat/stream"
data = {"query": "你好", "session_id": "test"}

response = requests.post(url, json=data, stream=True)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

### 预期输出格式

```
data: {"node": "Supervisor", "update": "...", "type": "progress"}
data: {"node": "Retriever", "update": "...", "type": "progress"}
data: {"node": "Generator", "update": "...", "type": "progress"}
data: {"type": "done"}
```

---

## 🔍 步骤 5: 调试与日志

### 查看请求日志

服务器会自动打印每个请求的日志：

```
[POST] /api/chat/stream - 200 - 1.234s
[GET] /api/db/sessions - 200 - 0.056s
```

### 开启详细日志

修改 `start_server.py`:

```python
uvicorn.run(
    "api.main:app",
    host="0.0.0.0",
    port=8000,
    reload=True,
    log_level="debug"  # 改为 debug
)
```

---

## ⚠️ 常见问题

### Q1: 导入错误 `ModuleNotFoundError: No module named 'src'`

**解决方案:** 确保在 `backend/` 目录下运行，或手动添加路径：

```python
import sys
sys.path.insert(0, '/Users/liuxinxin/Documents/GitHub/rag_agent')
```

### Q2: SSE 连接立即断开

**可能原因:**
1. Nginx 缓冲未禁用
2. 防火墙拦截长连接
3. 浏览器扩展干扰

**解决方案:** 使用 curl 或 Postman 测试，排除浏览器因素。

### Q3: CORS 错误

如果前端无法访问，检查 `api/main.py` 中的 CORS 配置：

```python
allow_origins=[
    "http://localhost:5173",  # Vue 开发端口
    "http://localhost:80"     # Nginx 生产端口
]
```

### Q4: LangGraph 状态错误

确保 `chat_graph.stream()` 的 `initial_state` 包含所有必需字段：

```python
initial_state = {
    "messages": [...],
    "next": "Supervisor",
    "session_id": "...",
    "kb_ids": [],
    "mode": "chat"
}
```

---

## 🎯 下一步计划

完成后端基础架构后，继续以下工作：

1. **文件上传接口** (`/api/read/upload`)
2. **PPT 生成接口** (`/api/ppt/generate`)
3. **知识库管理接口** (`/api/kb/*`)
4. **WebSocket 支持** (替代 SSE 的双向通信)
5. **JWT 认证** (用户登录/注册)

---

## 📝 目录结构总结

```
rag_agent/
├── backend/                          # 新增后端服务
│   ├── api/
│   │   ├── main.py                  # FastAPI 应用入口 ✅
│   │   ├── routes/
│   │   │   ├── chat_routes.py       # 聊天接口 ✅
│   │   │   └── db_routes.py         # 数据库接口 ✅
│   │   └── __init__.py
│   ├── src/                         # 原有核心逻辑 (需复制/链接)
│   ├── storage/                     # 数据存储
│   ├── requirements.txt             # Python 依赖 ✅
│   ├── start_server.py              # 启动脚本 ✅
│   ├── test_api.sh                  # 测试脚本 ✅
│   └── README.md                    # 使用文档 ✅
├── frontend/                        # 原 Streamlit 前端 (待替换为 Vue)
├── MIGRATION_PLAN.md                # 完整迁移计划 ✅
└── QUICK_START.md                   # 本文档 ✅
```

---

## 🎉 验收标准

确认以下功能正常工作：

- [ ] 后端服务成功启动
- [ ] 能够访问 Swagger UI (`/docs`)
- [ ] 健康检查接口返回 `{"status": "ok"}`
- [ ] 能够创建新会话
- [ ] 能够获取会话列表
- [ ] SSE 流式聊天接口正常响应
- [ ] 请求日志正确记录

**全部通过后，后端基础架构迁移完成！** ✅

---

## 💡 提示

1. **保持原项目不变**: 所有 `src/`, `skills/`, `storage/` 的修改都应该向后兼容
2. **逐步迁移**: 先保证核心聊天功能，再逐步添加其他模块
3. **充分测试**: 每个新接口都应该通过 Postman/curl 测试
4. **文档同步**: 及时更新 API 文档和使用说明

**当前进度**: 30% (后端基础完成)
**下一步**: 文件上传和下载接口
