<template>
  <div class="mastery-container">
    <!-- 左侧导航栏 -->
    <aside class="mastery-sidebar">
      <div class="sidebar-header">
        <el-button type="primary" :icon="Plus" @click="resetMastery" block>开始新学习</el-button>
      </div>
      
      <div class="sessions-list">
        <div class="list-title">学习记录</div>
        <div 
          v-for="s in sessions" 
          :key="s.id" 
          class="session-item"
          :class="{ active: currentSession?.id === s.id }"
          @click="loadSession(s.id)"
        >
          <el-icon><Notebook /></el-icon>
          <span class="topic-text">{{ s.topic }}</span>
          <el-button 
            class="delete-btn" 
            type="danger" 
            size="small" 
            :icon="Delete" 
            circle 
            @click.stop="handleDeleteSession(s.id)"
          />
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="mastery-main">
      <!-- 入口页 -->
      <div v-if="!currentSession" class="entry-page">
        <div class="entry-card">
          <h1>🎓 20/80 深度掌握引擎</h1>
          <p class="subtitle">二八定律：掌握 20% 的底层逻辑，推导 80% 的应用特性。</p>
          <div class="input-group">
            <el-input 
              v-model="newTopic" 
              placeholder="你想深度掌握什么？例如：比特币、React框架..." 
              size="large"
              @keyup.enter="startMastery"
            />
            <el-button type="primary" size="large" @click="startMastery" :loading="isStarting">
              降维打击
            </el-button>
          </div>
        </div>
      </div>

      <!-- 仪表盘 -->
      <div v-else class="dashboard">
        <header class="dashboard-header">
          <h2>🏷️ 主题：{{ currentSession.topic }}</h2>
        </header>

        <div class="dashboard-content">
          <!-- 概念列表 -->
          <div class="concept-nav">
            <div class="nav-title" style="display: flex; justify-content: space-between; align-items: center;">
              <span>核心节点</span>
              <div>
                <el-button link type="primary" size="small" @click="showAddDialog = true">➕ 添加</el-button>
                <el-button link type="success" size="small" @click="generateMore" :loading="isGeneratingMore">🌐 扩展</el-button>
              </div>
            </div>
            <div 
              v-for="concept in currentSession.concepts_data" 
              :key="concept.name"
              class="concept-btn"
              :class="{ 
                active: selectedConceptName === concept.name,
                completed: !!concept.detail 
              }"
              @click="selectConcept(concept)"
            >
              <el-icon v-if="concept.detail"><SuccessFilled /></el-icon>
              <el-icon v-else><CircleCheck /></el-icon>
              <span>{{ concept.name }}</span>
            </div>
          </div>

          <!-- 详情与对话 -->
          <div class="main-display">
            <div v-if="!selectedConceptName" class="empty-state">
              <el-empty description="请点击左侧核心概念开始深度学习" />
            </div>

            <template v-else>
              <!-- 详情卡片 -->
              <div v-loading="isExpanding" class="detail-card">
                <div v-if="currentConcept?.detail" class="detail-content">
                  <div class="concept-header">
                    <h3>🧩 {{ selectedConceptName }}</h3>
                    <el-alert :title="'💡 本质定义：' + currentConcept.detail.one_sentence_def" type="info" :closable="false" />
                  </div>

                  <div class="analogy-box">
                    <strong>🍎 神类比：</strong> {{ currentConcept.detail.analogy }}
                  </div>

                  <el-tabs v-model="activeTab" class="detail-tabs">
                    <el-tab-pane label="⚙️ 底层逻辑" name="logic">
                      <div class="tab-text markdown-body" v-html="renderMarkdown(currentConcept.detail.core_logic)"></div>
                    </el-tab-pane>
                    <el-tab-pane label="🤝 拓扑关系" name="relations">
                      <ul>
                        <li v-for="rel in currentConcept.detail.relationships" :key="rel">{{ rel }}</li>
                      </ul>
                    </el-tab-pane>
                    <el-tab-pane label="🌳 衍生特性" name="derivations">
                      <ul>
                        <li v-for="der in currentConcept.detail.derivations" :key="der">{{ der }}</li>
                      </ul>
                    </el-tab-pane>
                  </el-tabs>
                </div>
              </div>

              <!-- 对话区 -->
              <div v-if="currentConcept?.detail" class="chat-section">
                <h4>💬 深度追问</h4>
                <div class="chat-messages" ref="chatScroll">
                  <!-- 新增：空状态提示 -->
                  <div v-if="!currentConcept.chat_history?.length" class="chat-empty">
                    <el-icon size="40" color="#c0c4cc"><ChatLineRound /></el-icon>
                    <p>AI 导师已就位，基于当前概念有什么想深入了解的？请随时提问 👇</p>
                  </div>
                  
                  <!-- 原有聊天消息遍历 -->
                  <div v-for="(msg, idx) in currentConcept.chat_history" :key="idx" class="message" :class="msg.role">
                    <div class="message-bubble markdown-body" v-html="renderMarkdown(msg.content)"></div>
                  </div>
                </div>

                <!-- 猜你想问 -->
                <div class="suggestions" v-if="currentConcept.detail.suggested_questions?.length">
                  <span class="sugg-label">🤔 猜你想问：</span>
                  <el-button 
                    v-for="q in currentConcept.detail.suggested_questions" 
                    :key="q" 
                    size="small" 
                    round
                    @click="sendChatMessage(q)"
                  >
                    {{ q }}
                  </el-button>
                </div>

                <div class="chat-input">
                  <el-input 
                    v-model="chatInput" 
                    placeholder="输入你的问题..." 
                    @keyup.enter="sendChatMessage()"
                    :disabled="isChatting"
                  >
                    <template #append>
                      <el-button @click="sendChatMessage()" :loading="isChatting">发送</el-button>
                    </template>
                  </el-input>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </main>
    <!-- 手动添加概念弹窗 -->
    <el-dialog v-model="showAddDialog" title="手动添加核心节点" width="400px">
      <el-input v-model="customConceptName" placeholder="输入你想补充的专业术语/节点名称..." @keyup.enter="addCustomConcept" />
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addCustomConcept">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { Plus, Notebook, SuccessFilled, CircleCheck, Delete, ChatLineRound } from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import 'github-markdown-css/github-markdown.css'
import apiClient from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

// Markdown 配置
marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (text: string) => {
  return (marked as any)(text)
}

interface ConceptDetail {
  one_sentence_def: string
  analogy: string
  core_logic: string
  relationships: string[]
  derivations: string[]
  suggested_questions: string[]
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface Concept {
  name: string
  detail?: ConceptDetail
  chat_history?: ChatMessage[]
}

interface Session {
  id: string
  topic: string
  concepts_data: Concept[]
}

const sessions = ref<Session[]>([])
const currentSession = ref<Session | null>(null)
const newTopic = ref('')
const isStarting = ref(false)
const selectedConceptName = ref('')
const activeTab = ref('logic')
const isExpanding = ref(false)
const chatInput = ref('')
const isChatting = ref(false)
const chatScroll = ref<HTMLElement | null>(null)
const showAddDialog = ref(false)
const customConceptName = ref('')
const isGeneratingMore = ref(false)

const currentConcept = computed(() => {
  if (!currentSession.value || !selectedConceptName.value) return null
  return currentSession.value.concepts_data.find(c => c.name === selectedConceptName.value) || null
})

const fetchSessions = async () => {
  try {
    const resp: any = await apiClient.get('/api/mastery/sessions')
    sessions.value = resp.sessions || []
  } catch (e) {
    console.error('获取列表失败', e)
  }
}

const resetMastery = () => {
  currentSession.value = null
  selectedConceptName.value = ''
  chatInput.value = ''
  newTopic.value = ''
}

const handleDeleteSession = (sid: string) => {
  ElMessageBox.confirm('确定要删除这条学习记录吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    await apiClient.delete(`/api/mastery/session/${sid}`)
    ElMessage.success('已删除')
    if (currentSession.value?.id === sid) {
      resetMastery()
    }
    fetchSessions()
  })
}

const startMastery = async () => {
  if (!newTopic.value.trim()) return
  isStarting.value = true
  try {
    const resp: any = await apiClient.post('/api/mastery/session', { topic: newTopic.value })
    currentSession.value = {
      id: resp.session_id,
      topic: resp.topic,
      concepts_data: resp.core_concepts
    }
    newTopic.value = ''
    fetchSessions()
  } catch (e) {
    ElMessage.error('启动失败')
  } finally {
    isStarting.value = false
  }
}

const loadSession = async (sid: string) => {
  try {
    const resp: any = await apiClient.get(`/api/mastery/session/${sid}`)
    currentSession.value = {
      id: resp.id,
      topic: resp.topic,
      concepts_data: resp.concepts_data
    }
    selectedConceptName.value = ''
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const selectConcept = async (concept: Concept) => {
  selectedConceptName.value = concept.name
  if (!concept.detail) {
    isExpanding.value = true
    try {
      const resp: any = await apiClient.post('/api/mastery/expand', {
        session_id: currentSession.value!.id,
        concept_name: concept.name,
        topic: currentSession.value!.topic
      })
      concept.detail = resp.detail
      concept.chat_history = []
    } catch (e) {
      ElMessage.error('解构失败')
    } finally {
      isExpanding.value = false
    }
  }
}

const sendChatMessage = async (msg?: string) => {
  const content = msg || chatInput.value
  if (!content.trim() || isChatting.value) return
  
  if (!msg) chatInput.value = ''
  
  // 乐观更新
  currentConcept.value?.chat_history?.push({ role: 'user', content })
  scrollToBottom()
  
  isChatting.value = true
  try {
    const resp: any = await apiClient.post('/api/mastery/chat', {
      session_id: currentSession.value!.id,
      concept_name: selectedConceptName.value,
      topic: currentSession.value!.topic,
      message: content
    })
    if (currentConcept.value) {
      currentConcept.value.chat_history = resp.history
    }
    scrollToBottom()
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    isChatting.value = false
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatScroll.value) {
      chatScroll.value.scrollTop = chatScroll.value.scrollHeight
    }
  })
}

// 添加手动节点方法
const addCustomConcept = async () => {
  if (!customConceptName.value.trim() || !currentSession.value) return
  try {
    const resp: any = await apiClient.post('/api/mastery/add_concept', {
      session_id: currentSession.value.id,
      concept_name: customConceptName.value
    })
    currentSession.value.concepts_data = resp.concepts_data
    showAddDialog.value = false
    customConceptName.value = ''
    ElMessage.success('添加成功')
  } catch (e) {
    ElMessage.error('添加失败')
  }
}

// 联网扩展更多节点方法
const generateMore = async () => {
  if (!currentSession.value) return
  isGeneratingMore.value = true
  try {
    const resp: any = await apiClient.post('/api/mastery/generate_more', {
      session_id: currentSession.value.id
    })
    currentSession.value.concepts_data = resp.concepts_data
    ElMessage.success('已通过联网为您扩展了新的节点！')
  } catch (e) {
    ElMessage.error('扩展失败')
  } finally {
    isGeneratingMore.value = false
  }
}

onMounted(() => {
  fetchSessions()
})
</script>

<style scoped>
.mastery-container {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

.mastery-sidebar {
  width: 260px;
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
  padding: 15px 0;
}

.list-title {
  padding: 0 20px 10px;
  font-size: 12px;
  color: #909399;
  text-transform: uppercase;
}

.session-item {
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: background 0.2s;
  position: relative;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item .delete-btn {
  position: absolute;
  right: 10px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.session-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.topic-text {
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mastery-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.entry-page {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.entry-card {
  max-width: 600px;
  text-align: center;
}

.entry-card h1 {
  font-size: 32px;
  margin-bottom: 15px;
}

.subtitle {
  color: #606266;
  margin-bottom: 30px;
}

.input-group {
  display: flex;
  gap: 10px;
}

.dashboard {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.dashboard-header {
  padding: 15px 30px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.dashboard-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.concept-nav {
  width: 200px;
  background: #f8f9fa;
  border-right: 1px solid #e4e7ed;
  padding: 20px;
  overflow-y: auto;
}

.nav-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 15px;
}

.concept-btn {
  padding: 10px 15px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #dcdfe6;
  transition: all 0.2s;
  font-size: 14px;
}

.concept-btn:hover {
  border-color: #409eff;
  color: #409eff;
}

.concept-btn.active {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.concept-btn.completed .el-icon {
  color: #67c23a;
}

.concept-btn.active.completed .el-icon {
  color: #fff;
}

.main-display {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 30px;
}

.detail-card {
  background: #fff;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
  margin-bottom: 30px;
}

.concept-header {
  margin-bottom: 20px;
}

.concept-header h3 {
  margin-bottom: 15px;
}

.analogy-box {
  background: #f0f2f6;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 15px;
}

.detail-tabs {
  margin-top: 20px;
}

.tab-text {
  line-height: 1.6;
  white-space: pre-wrap;
}

.chat-section {
  background: #fff;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.chat-section h4 {
  margin-bottom: 15px;
}

.chat-messages {
  /* 删掉 height: 300px; 改为最小/最大高度限制 */
  min-height: 120px;
  max-height: 400px;
  overflow-y: auto;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 4px;
  margin-bottom: 20px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 0;
  color: #909399;
  text-align: center;
}

.chat-empty p {
  margin-top: 10px;
  font-size: 13px;
}

.message {
  margin-bottom: 15px;
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: 80%;
  padding: 10px 15px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.user .message-bubble {
  background: #409eff;
  color: #fff;
}

.assistant .message-bubble {
  background: #e4e7ed;
  color: #303133;
}

.suggestions {
  margin-bottom: 15px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.sugg-label {
  font-size: 13px;
  color: #909399;
}

.chat-input {
  margin-top: 10px;
}
</style>
