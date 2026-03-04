<template>
  <div class="skill-container">
    <!-- 消息列表 -->
    <main class="skill-main">
      <div class="messages-container" ref="msgScroll">
        <div 
          v-for="(msg, idx) in messages" 
          :key="idx" 
          class="message" 
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'"><User /></el-icon>
            <el-icon v-else><Cpu /></el-icon>
          </div>
          <div class="message-content">
            <!-- 普通消息文本 -->
            <div 
              v-if="msg.content" 
              class="message-text markdown-body" 
              v-html="renderMarkdown(msg.content)"
            ></div>
            
            <!-- 工具调用展示 -->
            <div v-if="msg.tool_calls?.length" class="tool-calls">
              <el-collapse v-model="activeTools" class="tool-collapse">
                <el-collapse-item 
                  v-for="(tool, tIdx) in msg.tool_calls" 
                  :key="tIdx"
                  :name="tool.id"
                >
                  <template #title>
                    <div class="tool-title">
                      <el-icon><MagicStick /></el-icon>
                      <span>调用工具: {{ tool.function.name }}</span>
                    </div>
                  </template>
                  <div class="tool-args">
                    <strong>参数:</strong>
                    <pre>{{ tool.function.arguments }}</pre>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 工具执行结果 -->
            <div v-if="msg.role === 'tool'" class="tool-result">
              <el-collapse class="tool-collapse">
                <el-collapse-item title="工具执行结果" :name="idx">
                  <div class="result-content">{{ msg.content }}</div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </div>

        <!-- 思考过程 (SSE) -->
        <div v-if="isLoading" class="loading-area">
          <el-progress :indeterminate="true" :stroke-width="2" />
          <div v-if="progressNodes.length" class="progress-list">
            <div v-for="(p, pIdx) in progressNodes" :key="pIdx" class="progress-node">
              <el-tag size="small" type="info">{{ p.node }}</el-tag>
              <span class="p-update">{{ p.update }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <footer class="input-footer">
        <div class="input-wrapper">
          <el-input 
            v-model="userInput" 
            type="textarea" 
            :rows="3" 
            placeholder="让智能体为你执行任务..." 
            @keyup.enter.native="sendMessage"
            :disabled="isLoading"
            resize="none"
          />
          <el-button 
            type="primary" 
            @click="sendMessage" 
            :loading="isLoading"
            class="send-btn"
          >
            执行
          </el-button>
        </div>
      </footer>
    </main>

    <!-- 右侧：可用工具列表 -->
    <aside class="skill-sidebar">
      <div class="sidebar-header-actions">
        <el-button type="danger" :icon="Refresh" @click="resetSession" style="width: 100%; margin-bottom: 20px;">
          重置会话
        </el-button>
      </div>
      <div class="sidebar-title">
        <el-icon><Tools /></el-icon>
        <span>可用工具</span>
      </div>
      <div class="skills-list">
        <el-card v-for="skill in availableSkills" :key="skill.name" class="skill-card" shadow="hover">
          <div class="skill-name">{{ skill.name }}</div>
          <div class="skill-desc">{{ skill.description }}</div>
        </el-card>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { User, Cpu, MagicStick, Tools, Refresh } from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import 'github-markdown-css/github-markdown.css'
import apiClient from '@/api'
import { ElMessage } from 'element-plus'

interface Skill {
  name: string
  description: string
}

interface Message {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: any[]
}

const availableSkills = ref<Skill[]>([])
const messages = ref<Message[]>([])
const userInput = ref('')
const isLoading = ref(false)
const progressNodes = ref<any[]>([])
const activeTools = ref<string[]>([])
const msgScroll = ref<HTMLElement | null>(null)
const sessionId = ref(`skill_${Math.random().toString(36).slice(2, 11)}`)

const resetSession = () => {
  messages.value = []
  progressNodes.value = []
  sessionId.value = `skill_${Math.random().toString(36).slice(2, 11)}`
  ElMessage.success('会话已重置')
}

// Markdown 配置
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderMarkdown = (text: string) => {
  // 处理图片链接，将 skills/*.png 转换为后端静态资源 URL
  const baseUrl = apiClient.defaults.baseURL || 'http://localhost:8000'
  const processedText = text.replace(
    /!\[(.*?)\]\((.*?\.png)\)/g, 
    (match, alt, path) => {
      if (path.startsWith('skills/')) {
        // 去掉开头的 skills/，保留后续路径
        const relativePath = path.replace(/^skills\//, '')
        return `![${alt}](${baseUrl}/static/skills/${relativePath})`
      }
      return match
    }
  )
  return (marked as any)(processedText)
}

const fetchSkills = async () => {
  try {
    const resp: any = await apiClient.get('/api/skill/list')
    availableSkills.value = resp.skills || []
  } catch (e) {
    console.error('获取工具列表失败')
  }
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return
  
  const query = userInput.value
  userInput.value = ''
  messages.value.push({ role: 'user', content: query })
  isLoading.value = true
  progressNodes.value = []
  scrollToBottom()

  try {
    const response = await fetch(`${apiClient.defaults.baseURL}/api/skill/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        query,
        session_id: sessionId.value 
      })
    })

    if (!response.body) return
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'progress') {
            progressNodes.value.push(data)
            
            // 如果是最终消息节点，将其加入 messages
            // 这里逻辑取决于 skill_graph 的返回格式，暂做简化处理
            if (data.node === 'Agent' && data.update.messages) {
              const lastMsg = data.update.messages[data.update.messages.length - 1]
              if (lastMsg.role === 'assistant') {
                 // 找到现有的 assistant 消息或创建新消息
                 let existing = null
                 for (let i = messages.value.length - 1; i >= 0; i--) {
                   if (messages.value[i].role === 'assistant') {
                     existing = messages.value[i]
                     break
                   }
                 }
                 
                 if (existing) {
                   existing.content = lastMsg.content
                   existing.tool_calls = lastMsg.tool_calls
                 } else {
                   messages.value.push({
                     role: 'assistant',
                     content: lastMsg.content,
                     tool_calls: lastMsg.tool_calls
                   })
                 }
              }
            }
            scrollToBottom()
          } else if (data.type === 'done') {
            isLoading.value = false
          }
        }
      }
    }
  } catch (e) {
    ElMessage.error('请求失败')
    isLoading.value = false
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (msgScroll.value) {
      msgScroll.value.scrollTop = msgScroll.value.scrollHeight
    }
  })
}

onMounted(() => {
  fetchSkills()
})
</script>

<style scoped>
.skill-container {
  display: flex;
  height: 100vh;
  background: #f0f2f5;
}

.skill-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

.messages-container {
  flex: 1;
  padding: 30px;
  overflow-y: auto;
}

.message {
  display: flex;
  gap: 15px;
  margin-bottom: 25px;
}

.message-avatar {
  font-size: 24px;
  color: #409eff;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecf5ff;
  border-radius: 8px;
}

.message-content {
  flex: 1;
  max-width: 85%;
}

.message-text {
  background: #f4f4f5;
  padding: 15px;
  border-radius: 8px;
  line-height: 1.6;
}

.user .message-text {
  background: #409eff;
  color: #fff;
}

.markdown-body {
  background-color: transparent !important;
  font-size: 14px;
}

.tool-calls {
  margin-top: 10px;
}

.tool-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
  color: #e6a23c;
}

.tool-args pre {
  background: #2d2d2d;
  color: #ccc;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
}

.tool-result {
  margin-top: 10px;
}

.result-content {
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  background: #f9f9f9;
  padding: 10px;
}

.loading-area {
  margin-top: 20px;
}

.progress-list {
  margin-top: 15px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
}

.progress-node {
  margin-bottom: 8px;
  font-size: 13px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.input-footer {
  padding: 20px 30px;
  border-top: 1px solid #e4e7ed;
}

.input-wrapper {
  display: flex;
  gap: 15px;
  align-items: flex-end;
}

.send-btn {
  height: 80px;
  width: 100px;
}

.skill-sidebar {
  width: 300px;
  background: #f8f9fa;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.sidebar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: bold;
  margin-bottom: 20px;
  color: #303133;
}

.skills-list {
  flex: 1;
  overflow-y: auto;
}

.skill-card {
  margin-bottom: 15px;
}

.skill-name {
  font-weight: bold;
  margin-bottom: 8px;
  color: #409eff;
}

.skill-desc {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}
</style>
