<template>
  <div class="chat-container">
    <!-- 左侧边栏：历史记录 + 知识库选择 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <el-button type="primary" @click="newChat" :icon="Plus">
          新建对话
        </el-button>
      </div>

      <div class="kb-selector">
        <div class="kb-selector-label">知识库过滤</div>
        <el-select
          v-model="selectedKbNames"
          multiple
          filterable
          collapse-tags
          placeholder="选择用于本轮对话的知识库"
          size="small"
        >
          <el-option
            v-for="kb in availableKbs"
            :key="kb"
            :label="kb"
            :value="kb"
          />
        </el-select>
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
            <div
              class="message-text markdown-body"
              v-html="renderMarkdown(splitContent(msg).body)"
            ></div>

            <!-- 引用与调研过程折叠展示，仅对助手消息开启 -->
            <el-collapse
              v-if="msg.role === 'assistant' && splitContent(msg).appendix"
              class="refs-collapse"
            >
              <el-collapse-item title="引用与调研过程" name="refs">
                <div
                  class="refs-content markdown-body"
                  v-html="renderMarkdown(splitContent(msg).appendix || '')"
                ></div>
              </el-collapse-item>
            </el-collapse>
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
import { ref, onMounted, nextTick } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import type { SSEEvent } from '@/api/chat'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import 'github-markdown-css/github-markdown.css'
import { Plus, Delete, User, Service, Loading, ChatDotRound } from '@element-plus/icons-vue'
import apiClient from '@/api'

const chatStore = useChatStore()
const inputMessage = ref('')
const availableKbs = ref<string[]>([])
const selectedKbNames = ref<string[]>([])

// Markdown 渲染配置
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: function (code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language }).value
  },
})

const renderMarkdown = (text: string) => {
  return marked(text)
}

// 将 Answerer 追加的“调查笔记 / 原始片段”从正文中分离出来，方便折叠展示
const splitContent = (msg: { content: string }) => {
  const text = msg.content || ''
  // 以第一个“调查笔记”或“原始片段”分隔，保持与后端约定的格式兼容
  const markers = ['【🕵️‍♂️ 调查笔记】', '【📚 原始片段】']
  let idx = -1
  for (const m of markers) {
    const pos = text.indexOf(m)
    if (pos !== -1) {
      idx = idx === -1 ? pos : Math.min(idx, pos)
    }
  }

  if (idx === -1) {
    return { body: text, appendix: '' }
  }
  return {
    body: text.slice(0, idx).trim(),
    appendix: text.slice(idx).trim(),
  }
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
  
  await chatStore.sendMessage(query, onProgress, selectedKbNames.value)
}

onMounted(async () => {
  await chatStore.loadSessions()
  // 加载可用知识库列表，用于多选过滤
  try {
    const resp = await apiClient.get('/api/kb/list')
    availableKbs.value = resp.kbs || []
  } catch (e) {
    console.error('加载知识库列表失败:', e)
  }
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

.kb-selector {
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
}

.kb-selector-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
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

/* 覆盖 github-markdown-css 的背景色，使其与消息框背景一致 */
.markdown-body {
  background-color: transparent !important;
  font-size: 14px;
}

.markdown-body :deep(pre) {
  background-color: #f6f8fa;
}

.loading-message {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-top: 10px;
}

.refs-collapse {
  margin-top: 10px;
}

.refs-content {
  font-size: 13px;
  line-height: 1.6;
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
