# DeepSeek RAG Agent - Vue 3 Frontend

基于 Vue 3 + Vite + TypeScript 的前端项目，用于替代原 Streamlit 界面。

## 🚀 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

复制环境变量配置文件：

```bash
cp .env.example .env
```

### 3. 启动开发服务器

确保后端服务已启动（端口 8000），然后运行：

```bash
npm run dev
```

访问 http://localhost:5173

## 📁 项目结构

```
frontend/
├── src/
│   ├── api/              # API 接口封装
│   │   ├── index.ts      # Axios 实例
│   │   └── chat.ts       # 聊天相关接口
│   ├── stores/           # Pinia 状态管理
│   │   └── chatStore.ts  # 聊天状态
│   ├── views/            # 页面视图
│   │   ├── ChatView.vue  # 聊天页面
│   │   └── ...
│   ├── router/           # 路由配置
│   │   └── index.ts
│   ├── components/       # 复用组件
│   ├── App.vue           # 根组件
│   └── main.ts           # 入口文件
├── package.json
├── vite.config.ts
├── tsconfig.json
└── README.md
```

## 🎯 核心功能

### 1. 智能对话 (Chat)

- ✅ SSE 流式实时响应
- ✅ 思考过程可视化
- ✅ Markdown 渲染
- ✅ 会话历史管理
- ✅ 多会话切换

### 2. 深度阅读 (DeepRead)

- ⏳ PDF 文件上传
- ⏳ 文档分析进度展示
- ⏳ 分析报告生成

### 3. 深度写作 (DeepWrite)

- ⏳ 多步骤写作流程
- ⏳ 内容大纲编辑
- ⏳ 自动生成文章

### 4. 知识库管理 (KBManagement)

- ⏳ 知识库列表
- ⏳ 创建/删除知识库
- ⏳ 文档上传与管理

### 5. PPT 生成 (PPTGenerator)

- ⏳ PPT 大纲编辑
- ⏳ 实时预览
- ⏳ 下载 PPTX 文件

## 🔧 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **Vite** - 下一代前端构建工具
- **TypeScript** - JavaScript 的超集
- **Pinia** - Vue 官方状态管理库
- **Vue Router** - 官方路由管理器
- **Element Plus** - 基于 Vue 3 的组件库
- **Axios** - HTTP 客户端
- **@microsoft/fetch-event-source** - SSE 客户端
- **Marked** - Markdown 解析器
- **Highlight.js** - 代码高亮

## 📝 API 接口

所有 API 请求通过 Axios 拦截器统一处理：

- **基础 URL**: `http://localhost:8000`
- **超时时间**: 30 秒
- **认证**: Bearer Token (可选)

### 主要接口

```typescript
// 流式聊天
chatStream(request, onMessage, onError, onClose)

// 获取会话列表
getSessions()

// 创建会话
createSession(title, mode)

// 获取消息历史
getSessionMessages(sessionId)

// 删除会话
deleteSession(sessionId)
```

## 🐳 Docker 部署

### 开发环境

```bash
docker build -f Dockerfile.dev -t rag_frontend_dev .
docker run -p 5173:5173 rag_frontend_dev
```

### 生产环境

```bash
docker build -f Dockerfile.prod -t rag_frontend_prod .
docker run -p 80:80 rag_frontend_prod
```

## 🎨 UI 设计

遵循 Element Plus 设计规范，保持简洁现代的风格：

- 主色调：蓝色 (#409EFF)
- 背景色：浅灰 (#F5F7FA)
- 圆角：8px
- 阴影：轻微阴影增强层次感

## 📊 状态管理

使用 Pinia 进行全局状态管理：

### ChatStore

```typescript
interface ChatState {
  currentSessionId: string | null
  messages: Message[]
  sessions: any[]
  isLoading: boolean
  progressNodes: SSEEvent[]
  error: string | null
}
```

## 🔐 认证机制

当前版本暂未实现 JWT 认证，后续会添加：

1. 登录/注册页面
2. Token 存储与刷新
3. 路由守卫
4. 权限控制

## 🛠️ 开发注意事项

1. **TypeScript 类型安全**: 所有接口和状态都定义了明确的类型
2. **组件化**: 尽量拆分可复用组件
3. **错误处理**: API 请求都有统一的错误处理
4. **响应式设计**: 适配不同屏幕尺寸

## 📈 性能优化

- [ ] 路由懒加载
- [ ] 组件异步加载
- [ ] 虚拟滚动（长列表）
- [ ] 请求缓存
- [ ] 防抖节流

## 🎯 下一步计划

1. 完善其他页面（DeepRead、DeepWrite 等）
2. 添加 JWT 认证
3. 优化移动端体验
4. 添加单元测试
5. 性能监控与分析

## 📞 调试技巧

### Chrome DevTools

- Vue DevTools: 查看组件树和状态
- Network: 监控 API 请求
- Console: 查看日志

### VS Code 插件

- Volar (Vue 语言支持)
- ESLint
- Prettier

## 🙏 致谢

本项目迁移自原 Streamlit 版本的 RAG Agent，感谢所有贡献者！
