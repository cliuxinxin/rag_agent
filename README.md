# 🧠 DeepSeek RAG Pro (Agentic Workflow)

这是一个基于 DeepSeek V3、LangGraph 和 腾讯混元 Embeddings 构建的高级 Agentic RAG（代理式检索增强生成）系统。

它不仅仅是一个简单的问答机器人，而是一个具备元认知能力的研究助理。它能够自主拆解问题、反思信息缺口、多轮迭代搜索，并提供带有精确引用的深度回答。

![alt text](https://img.shields.io/badge/Python-3.10%2B-blue)
![alt text](https://img.shields.io/badge/Streamlit-Frontend-red)
![alt text](https://img.shields.io/badge/LangGraph-Agent-green)

## ✨ 核心特性

🕵️‍♂️ Supervisor-Worker 架构：由总管（Supervisor）动态规划任务，指派搜索员（Searcher）挖掘信息，最后由回答者（Answerer）汇总。

🔄 混合检索 & 重排序：结合 BM25（关键词）和 腾讯混元 Vector（语义），并使用 FlashRank 进行 Cross-Encoder 重排序，确保召回精准。

📓 调查笔记本机制：Agent 会维护一份调查笔记，记录每一轮的发现，防止长对话中的信息遗忘。

🛡️ 负反馈记忆：系统能记住"搜过什么但没找到"，避免死循环，懂得及时止损。

🖱️ 交互式体验：

- 悬浮引用：鼠标悬停在 [Ref] 上即可预览原文。
- 折叠详情：详细的调查过程和原始文档被折叠，保持界面清爽。
- 一键追问：自动生成基于知识库的后续问题，点击即可追问。

## 🛠️ 快速开始

### 1. 环境准备

你需要准备以下 API Key：

- DeepSeek API Key: 用于逻辑推理和生成。
- Tencent Hunyuan API Key: 用于高性能中文向量化。

在项目根目录创建 .env 文件：

```env
# DeepSeek 配置
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_BASE=https://api.deepseek.com

# 腾讯混元 Embedding 配置
HUNYUAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. 本地部署 (Python)

确保已安装 Python 3.10 或更高版本。

```bash
# 1. 克隆项目
git clone <你的项目地址>
cd deepseek-rag-pro

# 2. 创建并激活虚拟环境 (可选但推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行应用
streamlit run frontend/app.py
```

浏览器访问：http://localhost:8501

### 3. Docker 部署 (推荐)

确保已安装 Docker 和 Docker Compose。

```bash
# 1. 构建并启动容器
docker-compose up -d --build

# 2. 查看日志
docker-compose logs -f
```

浏览器访问：http://localhost:8501

注意：Docker 部署会自动挂载 ./storage 目录，确保持久化存储你的知识库数据。

## 📖 使用指南

### 📂 知识库管理

1. 点击侧边栏切换到 "⚙️ 知识库管理"。
2. 选择 "➕ 新建/追加知识"。
3. 输入知识库名称（如 paper_research）。
4. 上传 PDF/TXT 文件或直接粘贴文本。
5. 点击 "💾 开始处理并保存"。系统会自动进行切分（Chunk Size=800）、向量化并存储。

### 💬 智能问答

1. 切换回 "💬 对话" 模式。
2. 在侧边栏 "🧠 知识库选择" 中勾选刚才创建的库。
3. 在输入框提问，例如："这篇论文的核心贡献是什么？"
4. 观察思考过程：你可以看到 Agent 正在进行第几轮调研、发现了什么缺口。
5. 查看结果：
   - 悬停 [Ref X] 查看引用来源。
   - 点击底部的 "📚 查看调查笔记" 展开详细的推理过程。
   - 点击末尾的 建议问题按钮 进行追问。

## 📂 项目结构

```
.
├── frontend/
│   └── app.py           # Streamlit 前端入口，处理 UI 和交互
├── src/
│   ├── __init__.py
│   ├── graph.py         # LangGraph 图编排 (Supervisor/Worker 逻辑)
│   ├── nodes.py         # 核心节点逻辑 (Prompt 工程、决策逻辑)
│   ├── state.py         # Agent 状态定义 (记忆、笔记结构)
│   ├── storage.py       # 知识库存储 (FAISS + JSON)
│   ├── embeddings.py    # 腾讯混元 Embedding 封装
│   ├── bm25.py          # BM25 检索器封装
│   └── utils.py         # 文件加载与切分工具
├── storage/             # (自动生成) 存放向量库和元数据
├── .env                 # 配置文件
├── docker-compose.yml   # Docker 编排
├── Dockerfile           # Docker 镜像定义
└── requirements.txt     # Python 依赖
```

## ❓ 常见问题

**Q: 支持什么格式的文件？**
A: 目前支持 .pdf (基于 pypdf) 和 .txt 文件。

**Q: 为什么 Agent 有时候会搜好几轮？**
A: 这是 Agentic RAG 的特性。如果第一次搜索结果不完整（有 Gap），Supervisor 会自动决定换个角度再搜一次，直到信息充足或达到最大轮次限制。