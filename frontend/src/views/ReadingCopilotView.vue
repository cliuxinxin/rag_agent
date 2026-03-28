<template>
  <div class="reading-copilot" :class="themeClass">
    <!-- 顶部操作栏 -->
    <div class="top-bar">
      <el-button @click="showImportDialog = true" type="primary" :icon="Plus">导入长文本</el-button>
      <el-button @click="showSessions = !showSessions" :icon="List">历史项目</el-button>
      
      <div class="view-controls" v-if="currentSessionId">
        <el-button-group>
          <el-button @click="adjustFontSize(-1)" :icon="Minus">减小字号</el-button>
          <el-button @click="adjustFontSize(1)" :icon="Plus">增大字号</el-button>
        </el-button-group>
        
        <el-button-group class="theme-switcher">
          <el-button @click="currentTheme = 'light'" :type="currentTheme === 'light' ? 'primary' : ''">☀️ 日间</el-button>
          <el-button @click="currentTheme = 'paper'" :type="currentTheme === 'paper' ? 'primary' : ''">📜 羊皮纸</el-button>
          <el-button @click="currentTheme = 'dark'" :type="currentTheme === 'dark' ? 'primary' : ''">🌙 夜间</el-button>
        </el-button-group>
        
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content" v-if="currentSessionId">
      <!-- 左栏：大纲导航 + 知识图谱 -->
      <div class="sidebar-left">
        <el-tabs v-model="leftSidebarTab" type="border-card">
          <el-tab-pane label="📑 文章大纲" name="toc">
            <div class="toc-list">
              <div 
                v-for="(heading, index) in tableOfContents" 
                :key="index"
                class="toc-item"
                @click="scrollToHeading(heading.id)"
              >
                {{ heading.text }}
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 中栏：阅读区 -->
      <div 
        class="reading-area" 
        ref="readingAreaRef"
        @mouseup="handleTextSelection"
        @click="hideSelectionMenu"
        :style="{ fontSize: `${fontSize}px`, lineHeight: lineHeight }"
        :class="readingAreaClasses"
      >
        <div v-html="renderedMarkdown" class="markdown-content"></div>
      </div>

      <!-- 右栏：AI助教区 -->
      <div class="sidebar-right">
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 导读Tab -->
          <el-tab-pane label="💡 导读" name="guide">
            <div class="guide-card">
              <h4>📝 一句话总结</h4>
              <p>{{ sessionData?.summary_data?.summary || '加载中...' }}</p>
              
              <h4>✨ 核心看点</h4>
              <ul>
                <li v-for="(point, index) in sessionData?.summary_data?.takeaways || []" :key="index">
                  {{ point }}
                </li>
              </ul>
              
              <div class="meta-info">
                <span>📄 字数: {{ sessionData?.word_count || 0 }} 字</span>
                <span>⏱️ 阅读时间: {{ sessionData?.read_time || 0 }} 分钟</span>
              </div>
              
            </div>
          </el-tab-pane>
          
          <!-- 伴读问答Tab -->
          <el-tab-pane label="💬 伴读问答" name="chat">
            <div class="chat-container">
              <div class="chat-messages" ref="chatMessagesRef">
                <div 
                  v-for="(msg, index) in chatMessages" 
                  :key="index"
                  class="message-item"
                  :class="msg.role"
                >
                  <div v-if="msg.quote_text" class="quote-text">
                    <span class="quote-label">引用原文:</span>
                    <p>{{ msg.quote_text }}</p>
                  </div>
                  <div class="message-content">
                    {{ msg.content }}
                  </div>
                </div>
                <div v-if="isStreaming" class="message-item assistant">
                  <div class="message-content streaming">
                    {{ streamingContent }}<span class="cursor">▋</span>
                  </div>
                </div>
              </div>
              
              <div class="chat-input-area">
                <div v-if="pendingQuote" class="pending-quote">
                  <span>引用: {{ pendingQuote }}</span>
                  <el-button @click="pendingQuote = ''" type="text" :icon="Close" size="small"></el-button>
                </div>
                <el-input
                  v-model="userInput"
                  type="textarea"
                  :rows="2"
                  placeholder="输入你的问题..."
                  @keyup.enter="sendMessage"
                ></el-input>
                <el-button @click="sendMessage" type="primary" :disabled="!userInput.trim() && !pendingQuote">发送</el-button>
              </div>
            </div>
          </el-tab-pane>
          
        </el-tabs>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-else>
      <el-empty description="导入长文本开始AI伴读体验">
        <el-button @click="showImportDialog = true" type="primary" :icon="Plus">导入文本</el-button>
      </el-empty>
    </div>

    <!-- 划词悬浮菜单 -->
    <div 
      class="selection-menu" 
      v-if="showSelectionMenu"
      :style="{ left: menuPosition.x + 'px', top: menuPosition.y + 'px' }"
    >
      <el-button @click="executeAction('explain')" size="small">🔍 解释</el-button>
      <el-button @click="executeAction('translate')" size="small">🌐 翻译</el-button>
      <el-button @click="executeAction('summarize')" size="small">📝 总结</el-button>
      <el-button @click="executeAction('explain_5yr')" size="small">👶 5岁秒懂</el-button>
      <el-button @click="executeAction('extract_quote')" size="small">🔥 提炼金句</el-button>
      <el-button @click="quoteSelection" size="small">💬 发问</el-button>
    </div>

    <!-- 导入文本对话框 -->
    <el-dialog v-model="showImportDialog" title="导入长文本" width="600px">
      <el-input
        v-model="importText"
        type="textarea"
        :rows="15"
        placeholder="粘贴你要阅读的长文本..."
      ></el-input>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button @click="initCopilot" type="primary" :loading="isImporting">开始处理</el-button>
      </template>
    </el-dialog>

    <!-- 历史会话抽屉 -->
    <el-drawer v-model="showSessions" title="历史阅读项目" size="400px">
      <div class="session-list">
        <div 
          v-for="session in sessions" 
          :key="session.id"
          class="session-item"
          @click="loadSession(session.id)"
        >
          <div class="session-title">{{ session.title }}</div>
          <div class="session-meta">
            <span>{{ session.word_count }}字 · {{ session.read_time }}分钟</span>
            <span>{{ formatTime(session.created_at) }}</span>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick, watch } from 'vue'
import { Plus, List, Minus, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { marked } from 'marked'

// 状态
const showImportDialog = ref(false)
const showSessions = ref(false)
const importText = ref('')
const isImporting = ref(false)
const currentSessionId = ref('')
const sessionData = ref<any>(null)
const sessions = ref([])
const renderedMarkdown = ref('')
const tableOfContents = ref([])
const currentTheme = ref('light')
const fontSize = ref(16)
const lineHeight = ref(1.8)
const activeTab = ref('guide')
const chatMessages = ref<any[]>([])
const userInput = ref('')
const isStreaming = ref(false)
const streamingContent = ref('')
const pendingQuote = ref('')
const showSelectionMenu = ref(false)
const menuPosition = ref({ x: 0, y: 0 })
const selectedText = ref('')
const leftSidebarTab = ref('toc')

const readingAreaRef = ref<HTMLElement>()
const chatMessagesRef = ref<HTMLElement>()

// 计算属性
const themeClass = computed(() => `theme-${currentTheme.value}`)
const readingAreaClasses = computed(() => {
  return ''
})

// 方法
async function initCopilot() {
  if (!importText.value.trim()) {
    ElMessage.warning('请输入文本内容')
    return
  }
  
  isImporting.value = true
  try {
    const res = await axios.post('/api/copilot/init', {
      raw_text: importText.value
    })
    
    if (res.data.success) {
      ElMessage.success('文本处理成功')
      showImportDialog.value = false
      importText.value = ''
      await loadSession(res.data.session_id)
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '处理失败')
  } finally {
    isImporting.value = false
  }
}

async function loadSession(sessionId: string) {
  currentSessionId.value = sessionId
  showSessions.value = false
  
  try {
    const res = await axios.get(`/api/copilot/session/${sessionId}`)
    if (res.data.success) {
      sessionData.value = res.data.data
      chatMessages.value = res.data.data.messages
      
      // 渲染Markdown并生成大纲
      renderedMarkdown.value = marked(sessionData.value.markdown_content)
      generateTableOfContents(sessionData.value.markdown_content)
      
      
      activeTab.value = 'guide'
      scrollToBottom()
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载会话失败')
  }
}

function generateTableOfContents(markdown: string) {
  const headings = markdown.match(/^##\s+(.+)$/gm) || []
  tableOfContents.value = headings.map((heading, index) => {
    const text = heading.replace(/^##\s+/, '')
    return {
      id: `heading-${index}`,
      text: text
    }
  })
  
  // 给渲染后的HTML标题加上id
  nextTick(() => {
    const contentEl = readingAreaRef.value?.querySelector('.markdown-content')
    if (contentEl) {
      const h2Elements = contentEl.querySelectorAll('h2')
      h2Elements.forEach((el, index) => {
        el.id = `heading-${index}`
      })
    }
  })
}

function scrollToHeading(id: string) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function adjustFontSize(delta: number) {
  fontSize.value = Math.max(12, Math.min(24, fontSize.value + delta))
}

function handleTextSelection(e: MouseEvent) {
  const selection = window.getSelection()
  const text = selection?.toString().trim() || ''
  
  if (text && text.length > 0) {
    selectedText.value = text
    const range = selection?.getRangeAt(0)
    if (range) {
      const rect = range.getBoundingClientRect()
      menuPosition.value = {
        x: rect.left + window.scrollX + rect.width / 2 - 150,
        y: rect.top + window.scrollY - 50
      }
      showSelectionMenu.value = true
    }
  }
}

function hideSelectionMenu() {
  showSelectionMenu.value = false
}

async function executeAction(action: string) {
  hideSelectionMenu()
  activeTab.value = 'chat'
  
  try {
    isStreaming.value = true
    streamingContent.value = ''
    
    // 添加用户消息
    const userMsg = {
      role: 'user',
      content: getActionLabel(action),
      quote_text: selectedText.value
    }
    chatMessages.value.push(userMsg)
    
    await nextTick()
    scrollToBottom()
    
    // 发送请求
    const res = await fetch('/api/copilot/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        session_id: currentSessionId.value,
        query: getActionLabel(action),
        quote_text: selectedText.value,
        action: action
      })
    })
    
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    
    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.replace('data: ', '')
            if (data === '[DONE]') {
              break
            }
            try {
              const parsed = JSON.parse(data)
              streamingContent.value += parsed.content
              await nextTick()
              scrollToBottom()
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    }
    
    // 添加助手消息
    chatMessages.value.push({
      role: 'assistant',
      content: streamingContent.value,
      quote_text: selectedText.value
    })
  } catch (e: any) {
    ElMessage.error('请求失败: ' + e.message)
  } finally {
    isStreaming.value = false
    streamingContent.value = ''
  }
}

function getActionLabel(action: string): string {
  const labels: Record<string, string> = {
    'explain': '请解释这段内容',
    'translate': '请翻译这段内容',
    'summarize': '请总结这段内容',
    'explain_5yr': '请用5岁小孩能懂的方式解释这段内容',
    'extract_quote': '请把这段内容提炼成金句'
  }
  return labels[action] || action
}

function quoteSelection() {
  hideSelectionMenu()
  activeTab.value = 'chat'
  pendingQuote.value = selectedText.value
}

async function sendMessage() {
  if (!userInput.value.trim() && !pendingQuote.value) return
  
  const query = userInput.value.trim()
  const quote = pendingQuote.value
  
  userInput.value = ''
  pendingQuote.value = ''
  
  try {
    isStreaming.value = true
    streamingContent.value = ''
    
    // 添加用户消息
    const userMsg = {
      role: 'user',
      content: query,
      quote_text: quote
    }
    chatMessages.value.push(userMsg)
    
    await nextTick()
    scrollToBottom()
    
    // 发送请求
    const res = await fetch('/api/copilot/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        session_id: currentSessionId.value,
        query: query,
        quote_text: quote,
        action: 'question'
      })
    })
    
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    
    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.replace('data: ', '')
            if (data === '[DONE]') {
              break
            }
            try {
              const parsed = JSON.parse(data)
              streamingContent.value += parsed.content
              await nextTick()
              scrollToBottom()
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    }
    
    // 添加助手消息
    chatMessages.value.push({
      role: 'assistant',
      content: streamingContent.value,
      quote_text: quote
    })
  } catch (e: any) {
    ElMessage.error('请求失败: ' + e.message)
  } finally {
    isStreaming.value = false
    streamingContent.value = ''
  }
}

function scrollToBottom() {
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

async function loadSessions() {
  try {
    const res = await axios.get('/api/copilot/sessions')
    if (res.data.success) {
      sessions.value = res.data.data
    }
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}


function formatTime(timeStr: string): string {
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}


// 生命周期
onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.reading-copilot {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-color);
  color: var(--text-color);
  transition: all 0.3s ease;
}

/* 主题变量 */
.theme-light {
  --bg-color: #ffffff;
  --text-color: #333333;
  --sidebar-bg: #f5f5f5;
  --reading-bg: #ffffff;
  --border-color: #e4e7ed;
}

.theme-paper {
  --bg-color: #f8f1e4;
  --text-color: #5a4a3f;
  --sidebar-bg: #f0e6d6;
  --reading-bg: #f8f1e4;
  --border-color: #d8cbb9;
}

.theme-dark {
  --bg-color: #1a1a1a;
  --text-color: #e0e0e0;
  --sidebar-bg: #2d2d2d;
  --reading-bg: #1a1a1a;
  --border-color: #404040;
}

.top-bar {
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 12px;
  background-color: var(--bg-color);
}

.view-controls {
  margin-left: auto;
  display: flex;
  gap: 16px;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左栏 */
.sidebar-left {
  width: 20%;
  min-width: 200px;
  padding: 20px;
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  background-color: var(--sidebar-bg);
}

.sidebar-left h3 {
  margin-bottom: 16px;
  font-size: 16px;
}

.toc-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toc-item {
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 14px;
}

.toc-item:hover {
  background-color: rgba(64, 158, 255, 0.1);
}

.sidebar-left :deep(.el-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-left :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.sidebar-left :deep(.el-tab-pane) {
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}


/* 中栏阅读区 */
.reading-area {
  width: 50%;
  flex: 1;
  padding: 40px 60px;
  overflow-y: auto;
  background-color: var(--reading-bg);
}

.markdown-content {
  max-width: 700px;
  margin: 0 auto;
}

.markdown-content h2 {
  margin: 40px 0 20px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--border-color);
  font-size: 24px;
}

.markdown-content p {
  margin-bottom: 1.5em;
  line-height: 1.8;
}

.markdown-content strong {
  color: var(--el-color-primary);
  font-weight: 600;
}


/* 右栏 */
.sidebar-right {
  width: 30%;
  min-width: 300px;
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background-color: var(--sidebar-bg);
}

.sidebar-right :deep(.el-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-right :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.sidebar-right :deep(.el-tab-pane) {
  height: 100%;
}

.guide-card {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.guide-card h4 {
  margin: 20px 0 12px 0;
  font-size: 15px;
}

.guide-card p {
  line-height: 1.6;
  margin-bottom: 12px;
}

.guide-card ul {
  padding-left: 20px;
  margin-bottom: 20px;
}

.guide-card li {
  margin-bottom: 8px;
  line-height: 1.5;
}

.meta-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 20px;
  padding: 12px;
  background-color: rgba(64, 158, 255, 0.05);
  border-radius: 4px;
  font-size: 13px;
}


/* 聊天区域 */
.chat-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-item {
  max-width: 90%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-item.user {
  align-self: flex-end;
}

.message-item.assistant {
  align-self: flex-start;
}

.quote-text {
  padding: 8px 12px;
  background-color: rgba(101, 198, 88, 0.1);
  border-left: 3px solid var(--el-color-success);
  border-radius: 0 4px 4px 0;
  font-size: 13px;
}

.quote-label {
  font-weight: 600;
  color: var(--el-color-success);
}

.quote-text p {
  margin: 4px 0 0 0;
  font-size: 13px;
  line-height: 1.4;
}

.message-content {
  padding: 10px 14px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 14px;
}

.message-item.user .message-content {
  background-color: var(--el-color-primary);
  color: white;
  border-bottom-right-radius: 4px;
}

.message-item.assistant .message-content {
  background-color: var(--el-color-info-light-9);
  color: var(--text-color);
  border-bottom-left-radius: 4px;
}

.streaming .cursor {
  animation: blink 1s infinite;
  color: var(--el-color-primary);
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.chat-input-area {
  padding: 16px;
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-color);
}

.pending-quote {
  padding: 8px 12px;
  margin-bottom: 12px;
  background-color: rgba(250, 173, 20, 0.1);
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.chat-input-area :deep(.el-textarea) {
  margin-bottom: 12px;
}

/* 划词菜单 */
.selection-menu {
  position: absolute;
  z-index: 9999;
  background-color: #303133;
  padding: 6px;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  display: flex;
  gap: 4px;
}

.selection-menu .el-button {
  color: white;
  background: transparent;
  border: none;
}

.selection-menu .el-button:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 历史会话列表 */
.session-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.session-item {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
}

.session-item:hover {
  border-color: var(--el-color-primary);
  background-color: rgba(64, 158, 255, 0.05);
}

.session-title {
  font-weight: 500;
  margin-bottom: 8px;
  font-size: 15px;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

</style>
