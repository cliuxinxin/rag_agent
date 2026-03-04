#!/bin/bash
# FastAPI 后端接口测试脚本

BASE_URL="http://localhost:8000"

echo "======================================"
echo "🧪 RAG Agent API 测试脚本"
echo "======================================"
echo ""

# 1. 健康检查
echo "1️⃣  健康检查..."
curl -s "$BASE_URL/health" | jq .
echo ""

# 2. 获取 API 信息
echo "2️⃣  获取 API 信息..."
curl -s "$BASE_URL/" | jq .
echo ""

# 3. 创建新会话
echo "3️⃣  创建新会话..."
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/db/sessions?title=测试会话&mode=chat")
echo "$SESSION_RESPONSE" | jq .
SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id')
echo "会话 ID: $SESSION_ID"
echo ""

# 4. 获取会话列表
echo "4️⃣  获取会话列表..."
curl -s "$BASE_URL/api/db/sessions" | jq .
echo ""

# 5. 发送流式聊天请求（非阻塞测试）
echo "5️⃣  测试流式聊天接口 (显示前 5 行)..."
if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "null" ]; then
    curl -s -X POST "$BASE_URL/api/chat/stream" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"你好，请介绍一下你自己\", \"session_id\": \"$SESSION_ID\"}" | head -n 5
else
    echo "❌ 会话创建失败，跳过流式测试"
fi
echo ""

# 6. 获取会话消息
echo "6️⃣  获取会话消息..."
if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "null" ]; then
    curl -s "$BASE_URL/api/db/sessions/$SESSION_ID/messages" | jq .
else
    echo "❌ 无效会话 ID"
fi
echo ""

# 7. 删除测试会话
echo "7️⃣  删除测试会话..."
if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "null" ]; then
    curl -s -X DELETE "$BASE_URL/api/db/sessions/$SESSION_ID" | jq .
else
    echo "❌ 无效会话 ID"
fi
echo ""

echo "======================================"
echo "✅ 测试完成!"
echo "======================================"
echo ""
echo "📌 提示:"
echo "   - 确保后端服务已启动：python start_server.py"
echo "   - 需要安装 jq: brew install jq (macOS) 或 apt-get install jq (Linux)"
echo "   - 完整 API 文档：$BASE_URL/docs"
