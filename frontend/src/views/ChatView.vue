<template>
  <div class="chat-container">
    <!-- 左侧边栏：历史记录 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <el-button type="primary" @click="newChat" :icon="Plus">
          新建对话
        </el-button>
      </div>
      
      <div class="sessions-list">
        <el-menu
          :default-active="currentSessionId"
          @select="loadSession"
        >
          <el-menu-item
            v-for="session in chatStore.sessions"
            :key="session.id"
            :index="session.id"
          >
            <span>{{ session.title }}</span>
            <template #append>
              <el-icon @click.stop="deleteSession(session.id)"><Delete /></el-icon>
            </template>
          </el-menu-item>
        </el-menu>
      </div>
    </aside>

    <!-- 主聊天区域 -->
    <main class="chat-main">
      <!-- 消息列表 -->
      <div class="messages-container">
        <div
          v-for="(msg, idx) in chatStore.messages"
          :key="idx"
          class="message"
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'"><User /></el-icon>
            <el-icon v-else><Service /></el-icon>
          </div>
          <div class="message-content">
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
          </div>
        </div>

        <!-- 加载中提示 -->
        <div v-if="chatStore.isLoading" class="loading-message">
          <el-progress :indeterminate="true" :stroke-width="2" />
          
          <!-- 思考过程展示 -->
          <el-collapse v-if="chatStore.progressNodes.length > 0" class="progress-collapse">
            <el-collapse-item title="思考过程" name="1">
              <div
                v-for="(node, idx) in chatStore.progressNodes"
                :key="idx"
                class="progress-item"
              >
                <el-tag size="small" type="info">{{ node.node }}</el-tag>
                <span>{{ node.update }}</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入你的问题..."
          @keyup.enter="sendMessage"
          :disabled="chatStore.isLoading"
          resize="none"
        />
        <el-button
          type="primary"
          @click="sendMessage"
          :loading="chatStore.isLoading"
          :icon="chatStore.isLoading ? Loading : ChatDotRound"
        >
          {{ chatStore.isLoading ? '思考中...' : '发送' }}
        </el-button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import type { SSEEvent } from '@/api/chat'
import { marked } from 'marked'
import { Plus, Delete, User, Service, Loading, ChatDotRound } from '@element-plus/icons-vue'

const chatStore = useChatStore()
const inputMessage = ref('')

// Markdown 渲染配置
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderMarkdown = (text: string) => {
  return marked(text)
}

const newChat = async () => {
  await chatStore.createNewSession('新对话', 'chat')
}

const loadSession = (sessionId: string) => {
  chatStore.loadSessionMessages(sessionId)
}

const deleteSession = async (sessionId: string) => {
  try {
    await chatStore.removeSession(sessionId)
  } catch (err) {
    console.error('删除失败:', err)
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim()) return
  
  const query = inputMessage.value
  inputMessage.value = ''
  
  // 显示进度更新
  const onProgress = (event: SSEEvent) => {
    console.log('进度更新:', event)
  }
  
  await chatStore.sendMessage(query, onProgress)
}

onMounted(async () => {
  await chatStore.loadSessions()
})
</script>

<style scoped>
.chat-container {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

.sidebar {
  width: 280px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.sessions-list {
  flex: 1;
  overflow-y: auto;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  display: flex;
  margin-bottom: 20px;
  padding: 15px;
  border-radius: 8px;
}

.message.user {
  background: #ecf5ff;
  margin-left: 60px;
}

.message.assistant {
  background: #f5f7fa;
  margin-right: 60px;
}

.message-avatar {
  font-size: 24px;
  color: #409eff;
  margin-right: 12px;
}

.message-content {
  flex: 1;
}

.message-text {
  line-height: 1.6;
}

.loading-message {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-top: 10px;
}

.progress-collapse {
  margin-top: 15px;
  background: #fff;
}

.progress-item {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.input-area {
  padding: 20px;
  border-top: 1px solid #e4e7ed;
  display: flex;
  gap: 10px;
  background: #fff;
}

.input-area :deep(.el-input__wrapper) {
  flex: 1;
}
</style>
