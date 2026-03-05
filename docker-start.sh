#!/bin/bash
# Docker Compose 快速启动脚本

echo "======================================"
echo "🐳 RAG Agent - Docker 部署"
echo "======================================"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：未找到 Docker，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误：未找到 Docker Compose，请先安装"
    exit 1
fi

echo "✅ Docker 版本：$(docker --version)"
echo "✅ Docker Compose 版本：$(docker-compose --version)"
echo ""

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "   请复制 .env.example 并配置必要的环境变量"
    cp .env.example .env 2>/dev/null || true
    echo ""
fi

# 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down --remove-orphans 2>/dev/null

# 构建并启动
echo "🚀 开始构建并启动服务..."
docker-compose up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "✅ 启动成功!"
    echo "======================================"
    echo ""
    echo "📌 访问地址:"
    echo "   前端界面：http://localhost:80"
    echo "   后端 API: http://localhost:8000"
    echo "   API 文档：http://localhost:8000/docs"
    echo ""
    echo "🔧 常用命令:"
    echo "   查看日志：docker-compose logs -f"
    echo "   停止服务：docker-compose down"
    echo "   重启服务：docker-compose restart"
    echo ""
else
    echo ""
    echo "❌ 启动失败，请检查错误信息"
    exit 1
fi
