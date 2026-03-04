# Streamlit 到 Vue 3 迁移实施指南

## 📋 项目概述

**目标**: 将基于 Streamlit 的 RAG Agent 项目迁移到前后端分离架构 (FastAPI + Vue 3)

**核心变化**:
- **旧架构**: Streamlit UI ←→ st.session_state ←→ LangGraph/DB
- **新架构**: Vue 3 UI ←→ Axios/SSE ←→ FastAPI ←→ LangGraph/DB

---

## 🏗️ 第一阶段：架构重构设计

### 技术栈选择

**后端**:
- FastAPI (Web 框架)
- Uvicorn (ASGI 服务器)
- python-multipart (文件上传)
- python-jose + passlib (JWT 认证)

**前端**:
- Vue 3 + TypeScript
- Vite (构建工具)
- Pinia (状态管理)
- Vue Router (路由)
- Element Plus (UI 组件库)
- Axios + EventSource (HTTP/SSE 通信)

### 目录结构规划

```
rag_agent/
├── backend/                 # Python 后端
│   ├── api/                 # FastAPI 路由层 (新增)
│   │   ├── main.py         # FastAPI 启动入口
│   │   ├── auth.py         # 认证接口
│   │   └── routes/
│   │       ├── chat_routes.py    # 聊天流式接口
│   │       ├── db_routes.py      # 数据库 CRUD
│   │       ├── read_routes.py    # DeepRead 接口
│   │       ├── ppt_routes.py     # PPT 生成接口
│   │       └── kb_routes.py      # 知识库管理
│   ├── src/                # 原有核心逻辑 (保持不变)
│   │   ├── graphs/
│   │   ├── nodes/
│   │   ├── tools/
│   │   ├── skills/
│   │   └── ...
│   ├── skills/             # 技能包 (保持不变)
│   ├── storage/            # SQLite/FAISS (保持不变)
│   ├── config.yaml         # 配置文件
│   ├── requirements.txt    # 依赖 (更新)
│   └── .env               # 环境变量
│
├── frontend/               # Vue 3 前端 (全新)
│   ├── src/
│   │   ├── api/           # Axios 封装
│   │   │   ├── index.ts
│   │   │   ├── chat.ts
│   │   │   ├── db.ts
│   │   │   └── ...
│   │   ├── components/    # 复用组件
│   │   │   ├── MarkdownViewer.vue
│   │   │   ├── StatusBox.vue
│   │   │   └── ...
│   │   ├── views/         # 页面视图
│   │   │   ├── ChatView.vue
│   │   │   ├── DeepReadView.vue
│   │   │   ├── DeepWriteView.vue
│   │   │   ├── KBManagement.vue
│   │   │   └── ...
│   │   ├── stores/        # Pinia 状态管理
│   │   │   ├── chatStore.ts
│   │   │   ├── userStore.ts
│   │   │   └── ...
│   │   └── router/        # 路由配置
│   │       └── index.ts
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── docker-compose.yml      # 多服务编排
├── Dockerfile.backend      # 后端镜像
└── Dockerfile.frontend     # 前端镜像
```

---

## 🔧 第二阶段：Python 后端改造

### 步骤 1: 安装 FastAPI 依赖

```bash
pip install fastapi uvicorn python-multipart \
            python-jose[cryptography] passlib[bcrypt] \
            pydantic-settings
```

### 步骤 2: 创建 API 路由层

#### 2.1 主入口 (api/main.py)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import chat_routes, db_routes, read_routes, ppt_routes, kb_routes

app = FastAPI(title="RAG Agent API", version="1.0")

# CORS 配置 (允许前端跨域访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80"],  # Vue 开发服务器和 Nginx
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_routes.router, prefix="/api/chat", tags=["聊天"])
app.include_router(db_routes.router, prefix="/api/db", tags=["数据库"])
app.include_router(read_routes.router, prefix="/api/read", tags=["深度阅读"])
app.include_router(ppt_routes.router, prefix="/api/ppt", tags=["PPT 生成"])
app.include_router(kb_routes.router, prefix="/api/kb", tags=["知识库"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

#### 2.2 流式聊天接口 (api/routes/chat_routes.py)

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
from src.graphs.chat_graph import chat_graph

router = APIRouter()

@router.post("/stream")
async def chat_stream(request: dict):
    """
    流式聊天接口 (SSE)
    请求体: {
        "query": "用户问题",
        "session_id": "会话 ID",
        "mode": "chat|deep_qa|..."
    }
    """
    query = request.get("query")
    session_id = request.get("session_id", "default")
    
    if not query:
        raise HTTPException(status_code=400, detail="Missing query")
    
    # 构造初始状态 (参考原 chat.py 逻辑)
    initial_state = {
        "messages": [{"role": "user", "content": query}],
        "next": "Supervisor",
        "session_id": session_id,
        "kb_ids": request.get("kb_ids", []),
    }
    
    async def event_generator():
        """SSE 事件生成器"""
        try:
            for step in chat_graph.stream(initial_state, config={"recursion_limit": 50}):
                for node_name, update in step.items():
                    # 将节点更新包装成 SSE 格式
                    event_data = {
                        "node": node_name,
                        "update": str(update) if not isinstance(update, dict) else update,
                        "type": "progress"
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
            # 发送完成信号
            yield "data: {\"type\": \"done\"}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

#### 2.3 数据库接口 (api/routes/db_routes.py)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.db import get_all_sessions, get_messages, create_session, delete_session

router = APIRouter()

class SessionModel(BaseModel):
    session_id: Optional[str] = None
    title: str
    mode: str

@router.get("/sessions")
async def get_sessions():
    """获取所有会话列表"""
    sessions = get_all_sessions()
    return {"sessions": sessions}

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取指定会话的消息历史"""
    messages = get_messages(session_id)
    return {"messages": messages}

@router.post("/sessions")
async def create_new_session(session: SessionModel):
    """创建新会话"""
    session_id = create_session(session.title, session.mode)
    return {"session_id": session_id}

@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str):
    """删除会话"""
    delete_session(session_id)
    return {"status": "deleted"}
```

#### 2.4 文件上传接口 (api/routes/read_routes.py)

```python
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import tempfile
import os

router = APIRouter()

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 文件"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    # TODO: 调用原有的 PyPDFLoader 处理
    return {
        "filename": file.filename,
        "temp_path": tmp_path,
        "size": len(content)
    }

@router.post("/analyze")
async def analyze_document(file_path: str = Form(...), query: str = Form(...)):
    """分析文档并返回流式结果"""
    # TODO: 调用 deep_read_graph 的逻辑
    pass
```

#### 2.5 PPT 下载接口 (api/routes/ppt_routes.py)

```python
from fastapi import APIRouter, Response
from src.ppt_renderer import generate_ppt_bytes

router = APIRouter()

@router.post("/generate")
async def generate_ppt(request: dict):
    """生成 PPT 并返回二进制流"""
    outline = request.get("outline")
    topic = request.get("topic")
    
    # 调用原有的 PPT 生成逻辑
    ppt_bytes = generate_ppt_bytes(topic, outline)
    
    return Response(
        content=ppt_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{topic}.pptx"'
        }
    )
```

---

## 🎨 第三阶段：Vue 3 前端开发

### 步骤 1: 初始化项目

```bash
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
npm install vue-router pinia axios element-plus @iconify/vue marked highlight.js
```

### 步骤 2: 状态管理 (Pinia Store)

#### src/stores/chatStore.ts

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  // State
  const currentSessionId = ref<string | null>(null)
  const messages = ref<Array<{role: string, content: string}>>([])
  const selectedKBs = ref<number[]>([])
  const isLoading = ref(false)
  const progressNodes = ref<Array<{node: string, update: string}>>([])

  // Actions
  async function fetchHistory(sessionId: string) {
    const response = await fetch(`/api/db/sessions/${sessionId}/messages`)
    const data = await response.json()
    messages.value = data.messages
  }

  async function createSession(title: string, mode: string) {
    const response = await fetch('/api/db/sessions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title, mode})
    })
    const data = await response.json()
    currentSessionId.value = data.session_id
    return data.session_id
  }

  async function sendMessage(query: string) {
    isLoading.value = true
    progressNodes.value = []
    
    // 使用 EventSource 接收 SSE 流
    const eventSource = new EventSource(`/api/chat/stream?query=${encodeURIComponent(query)}&session_id=${currentSessionId.value}`)
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'progress') {
        progressNodes.value.push({node: data.node, update: data.update})
      } else if (data.type === 'done') {
        isLoading.value = false
        eventSource.close()
        // 重新加载消息历史
        if (currentSessionId.value) {
          fetchHistory(currentSessionId.value)
        }
      }
    }
    
    eventSource.onerror = () => {
      isLoading.value = false
      eventSource.close()
    }
  }

  return {
    currentSessionId,
    messages,
    selectedKBs,
    isLoading,
    progressNodes,
    fetchHistory,
    createSession,
    sendMessage
  }
})
```

### 步骤 3: 核心组件实现

#### ChatView.vue (对应原 chat.py)

```vue
<template>
  <div class="chat-container">
    <!-- 左侧边栏：历史记录 -->
    <aside class="sidebar">
      <el-button type="primary" @click="newChat">新建对话</el-button>
      <el-menu>
        <el-menu-item 
          v-for="session in sessions" 
          :key="session.id"
          @click="loadSession(session.id)">
          {{ session.title }}
        </el-menu-item>
      </el-menu>
    </aside>

    <!-- 主聊天区域 -->
    <main class="chat-main">
      <!-- 消息列表 -->
      <div class="messages">
        <div 
          v-for="(msg, idx) in chatStore.messages" 
          :key="idx"
          class="message"
          :class="msg.role">
          <strong>{{ msg.role }}:</strong>
          <div v-html="renderMarkdown(msg.content)"></div>
        </div>
        
        <!-- 加载中提示 -->
        <div v-if="chatStore.isLoading" class="loading">
          <el-progress :indeterminate="true" />
          
          <!-- 思考过程展示 -->
          <el-collapse>
            <el-collapse-item title="思考过程">
              <div 
                v-for="(node, idx) in chatStore.progressNodes" 
                :key="idx">
                <strong>{{ node.node }}:</strong> {{ node.update }}
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入问题..."
          @keyup.enter="sendMessage"
          :disabled="chatStore.isLoading">
        </el-input>
        <el-button 
          type="primary" 
          @click="sendMessage"
          :loading="chatStore.isLoading">
          发送
        </el-button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import { marked } from 'marked'

const chatStore = useChatStore()
const inputMessage = ref('')
const sessions = ref([])

const renderMarkdown = (text: string) => {
  return marked(text)
}

const newChat = async () => {
  await chatStore.createSession('新对话', 'chat')
  chatStore.messages = []
}

const loadSession = (id: string) => {
  chatStore.currentSessionId = id
  chatStore.fetchHistory(id)
}

const sendMessage = async () => {
  if (!inputMessage.value.trim()) return
  
  // 添加用户消息到本地显示
  chatStore.messages.push({
    role: 'user',
    content: inputMessage.value
  })
  
  // 发送到后端
  await chatStore.sendMessage(inputMessage.value)
  inputMessage.value = ''
}
</script>

<style scoped>
.chat-container {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 250px;
  border-right: 1px solid #e0e0e0;
  padding: 20px;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  margin-bottom: 20px;
  padding: 15px;
  border-radius: 8px;
}

.message.user {
  background: #f0f9ff;
}

.message.assistant {
  background: #f5f5f5;
}

.input-area {
  padding: 20px;
  border-top: 1px solid #e0e0e0;
}
</style>
```

---

## 🐳 第四阶段：Docker 部署配置

### Dockerfile.backend

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY backend/ .

# 创建存储目录
RUN mkdir -p storage

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile.frontend

```dockerfile
# 构建阶段
FROM node:18-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# 生产阶段 (Nginx)
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: rag_backend
    ports:
      - "8000:8000"
    volumes:
      - ./storage:/app/storage
    env_file:
      - .env
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    container_name: rag_frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

### frontend/nginx.conf

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # 反向代理 API 请求到后端
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE 支持
        proxy_cache off;
        proxy_buffering off;
        proxy_connect_timeout 1s;
        proxy_send_timeout 1s;
        proxy_read_timeout 30s;
    }
}
```

---

## 📝 实施顺序建议

### Week 1: 后端基础
1. ✅ 创建 FastAPI 项目结构
2. ✅ 实现聊天流式接口 (最难但最核心)
3. ✅ 用 Postman 测试 SSE 流

### Week 2: 前端骨架
1. ✅ 初始化 Vue 项目
2. ✅ 搭建 Layout (侧边栏 + 主界面)
3. ✅ 配置 Pinia 和 Router

### Week 3: 核心功能联调
1. ✅ 在 Vue 中接通 SSE 流
2. ✅ 实现聊天界面 (含思考过程展示)
3. ✅ Markdown 渲染

### Week 4: 其他模块迁移
1. ✅ 知识库管理 (CRUD + 上传)
2. ✅ 深度阅读 (PDF 解析 + 报告生成)
3. ✅ PPT 生成与下载

### Week 5: 完善与优化
1. ⏳ JWT 认证
2. ⏳ 错误处理
3. ⏳ 性能优化
4. ⏳ 样式美化

---

## 💡 关键技术点

### 1. SSE vs WebSocket
- **SSE**: 单向推送 (后端→前端)，更适合 LLM 流式输出
- **WebSocket**: 双向通信，适合实时交互场景

### 2. 流式数据处理
```typescript
// 使用 @microsoft/fetch-event-source (更稳定的 SSE 客户端)
import { fetchEventSource } from '@microsoft/fetch-event-source'

await fetchEventSource('/api/chat/stream', {
  method: 'POST',
  body: JSON.stringify({query, session_id}),
  onmessage: (event) => {
    const data = JSON.parse(event.data)
    // 处理节点更新
  },
  onclose: () => {
    // 连接关闭
  },
  onerror: (err) => {
    // 错误处理
  }
})
```

### 3. Markdown 渲染
```typescript
import { marked } from 'marked'
import hljs from 'highlight.js'

marked.setOptions({
  highlight: (code, lang) => hljs.highlightAuto(code).value
})
```

---

## 🎯 成功标准

- [ ] 能通过 Vue 界面进行流式对话
- [ ] 能看到 Supervisor/Nodes 的思考过程
- [ ] 能上传 PDF 并生成分析报告
- [ ] 能生成并下载 PPT
- [ ] 能管理知识库 (增删改查)
- [ ] Docker Compose 一键启动

---

**备注**: 本迁移计划保持原有 `src/`, `skills/`, `storage/` 的核心逻辑不变，仅替换 UI 层和增加 API 层，最大程度降低风险。
