#!/bin/bash
# Vue 前端项目快速启动脚本

echo "======================================"
echo "🚀 DeepSeek RAG Agent - 前端启动"
echo "======================================"
echo ""

# 检查 Node.js 版本
if ! command -v node &> /dev/null; then
    echo "❌ 错误：未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ 错误：Node.js 版本过低，需要 18+，当前版本：$(node -v)"
    exit 1
fi

echo "✅ Node.js 版本检查通过：$(node -v)"
echo ""

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 首次运行，正在安装依赖..."
    npm install
    
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请检查网络连接"
        exit 1
    fi
    echo "✅ 依赖安装完成"
    echo ""
fi

# 检查环境变量配置
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，正在从 .env.example 创建..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件"
    echo ""
fi

# 检查后端服务
echo "🔍 检查后端服务状态..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 后端服务正常运行"
else
    echo "⚠️  后端服务未启动，请先启动后端服务："
    echo "   cd backend && python start_server.py"
    echo ""
fi

echo "======================================"
echo "🎉 准备启动开发服务器..."
echo "======================================"
echo ""
echo "📌 访问地址：http://localhost:5173"
echo "📌 API 代理：http://localhost:8000"
echo "📌 按 Ctrl+C 停止服务"
echo ""

# 启动开发服务器
npm run dev
