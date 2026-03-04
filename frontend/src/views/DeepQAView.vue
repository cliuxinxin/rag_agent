<template>
  <div class="qa-container">
    <!-- 侧边栏：历史项目 + 知识库选择 -->
    <aside class="qa-sidebar">
      <div class="sidebar-header">
        <el-button type="primary" :icon="Plus" @click="createNewProject" block>创建 QA 项目</el-button>
      </div>

      <div class="kb-selector">
        <div class="section-title">知识库选择</div>
        <el-select
          v-model="selectedKbs"
          multiple
          filterable
          collapse-tags
          placeholder="选择相关知识库"
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

      <div class="history-list">
        <div class="section-title">历史项目</div>
        <div 
          v-for="(p, idx) in historyProjects" 
          :key="idx" 
          class="history-item"
          :class="{ active: currentProject?.title === p.title }"
          @click="loadProject(p)"
        >
          <el-icon><QuestionFilled /></el-icon>
          <span class="history-title">{{ p.title }}</span>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="qa-main">
      <!-- 入口：创建项目 -->
      <div v-if="!currentProject" class="entry-page">
        <el-card class="entry-card">
          <template #header>
            <div class="card-header">
              <h2>❓ 深度追问</h2>
              <p>系统性地深挖特定主题的所有疑难点</p>
            </div>
          </template>
          <el-form :model="newProjectForm" label-position="top">
            <el-form-item label="项目标题">
              <el-input v-model="newProjectForm.title" placeholder="给你的 QA 项目起个名字" />
            </el-form-item>
            <el-form-item label="主题/领域">
              <el-input 
                v-model="newProjectForm.topic" 
                type="textarea" 
                :rows="4" 
                placeholder="描述你要深入探讨的主题或领域..." 
              />
            </el-form-item>
            <el-button type="primary" @click="handleCreateProject" block>🚀 创建并开始</el-button>
          </el-form>
        </el-card>
      </div>

      <!-- 项目详情 -->
      <div v-else class="project-dashboard">
        <header class="project-header">
          <div class="header-left">
            <h2>{{ currentProject.title }}</h2>
            <el-tag type="info" size="small">{{ currentProject.topic }}</el-tag>
          </div>
          <el-button type="danger" plain size="small" @click="createNewProject">重置项目</el-button>
        </header>

        <div class="project-content">
          <!-- 已有问答列表 -->
          <div v-if="currentProject.qa_pairs.length" class="qa-history">
            <h3>💬 已有问答</h3>
            <el-collapse accordion>
              <el-collapse-item 
                v-for="(qa, idx) in currentProject.qa_pairs" 
                :key="idx" 
                :name="idx"
              >
                <template #title>
                  <div class="qa-title">
                    <el-tag size="small" class="qa-idx">Q{{ idx + 1 }}</el-tag>
                    <span>{{ qa.question }}</span>
                  </div>
                </template>
                <div class="qa-answer markdown-body" v-html="renderMarkdown(qa.answer)"></div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 新问题输入 -->
          <div class="new-question-area">
            <h3>❓ 提出新问题</h3>
            <el-input 
              v-model="newQuestion" 
              type="textarea" 
              :rows="4" 
              placeholder="请输入你想深入了解的问题..." 
              :disabled="isLoading"
            />
            <div class="action-bar">
              <el-button 
                type="primary" 
                @click="handleDeepAnalysis" 
                :loading="isLoading"
                :disabled="!newQuestion.trim() || !selectedKbs.length"
              >
                🔍 深度分析
              </el-button>
              <el-button 
                v-if="currentProject.qa_pairs.length" 
                type="success" 
                @click="generateFinalReport"
                :loading="isLoading"
              >
                📊 生成总结报告
              </el-button>
            </div>
          </div>

          <!-- 分析进度 -->
          <div v-if="isLoading" class="analysis-progress">
            <el-progress :indeterminate="true" :stroke-width="2" />
            <div class="progress-steps">
              <div v-for="(p, idx) in progressNodes" :key="idx" class="step-item">
                <el-icon class="is-loading" v-if="idx === progressNodes.length - 1"><Loading /></el-icon>
                <el-icon v-else color="#67C23A"><SuccessFilled /></el-icon>
                <span>{{ p.node }}: {{ p.msg }}</span>
              </div>
            </div>
          </div>

          <!-- 总结报告展示 -->
          <div v-if="currentProject.final_report" class="report-section">
            <h3>📝 总结报告</h3>
            <el-card shadow="never" class="report-card">
              <div class="markdown-body" v-html="renderMarkdown(currentProject.final_report)"></div>
            </el-card>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, QuestionFilled, Loading, SuccessFilled } from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import 'github-markdown-css/github-markdown.css'
import apiClient from '@/api'
import { ElMessage } from 'element-plus'

interface QAPair {
  question: string
  answer: string
}

interface Project {
  title: string
  topic: string
  qa_pairs: QAPair[]
  final_report: string
}

const availableKbs = ref<string[]>([])
const selectedKbs = ref<string[]>([])
const historyProjects = ref<Project[]>([])
const currentProject = ref<Project | null>(null)
const isLoading = ref(false)
const progressNodes = ref<any[]>([])
const newQuestion = ref('')

const newProjectForm = reactive({
  title: '',
  topic: ''
})

// Markdown 配置
marked.setOptions({
  breaks: true,
  gfm: true
})
const renderMarkdown = (text: string) => {
  return (marked as any)(text)
}

const fetchKbs = async () => {
  try {
    const resp: any = await apiClient.get('/api/kb/list')
    availableKbs.value = resp.kbs || []
  } catch (e) {
    console.error('获取知识库失败')
  }
}

const createNewProject = () => {
  currentProject.value = null
  newProjectForm.title = ''
  newProjectForm.topic = ''
}

const handleCreateProject = () => {
  if (!newProjectForm.title || !newProjectForm.topic) {
    ElMessage.warning('请完整填写项目信息')
    return
  }
  
  const project: Project = {
    title: newProjectForm.title,
    topic: newProjectForm.topic,
    qa_pairs: [],
    final_report: ''
  }
  
  currentProject.value = project
  historyProjects.value.unshift(project)
}

const loadProject = (p: Project) => {
  currentProject.value = p
}

const handleDeepAnalysis = async () => {
  if (!newQuestion.value.trim() || !selectedKbs.value.length) return
  
  const query = newQuestion.value
  isLoading.value = true
  progressNodes.value = []
  
  try {
    const response = await fetch(`${apiClient.defaults.baseURL}/api/qa/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        kb_names: selectedKbs.value,
        history: currentProject.value?.qa_pairs || []
      })
    })

    if (!response.body) return
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalAnswer = ''

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
            // 更新进度节点
            const msg = typeof data.update === 'string' ? data.update : (data.update.messages?.[0]?.content || '处理中...')
            progressNodes.value.push({ node: data.node, msg: msg })
            
            // 如果是写入节点，更新最终答案
            if (data.node === 'QAWriter' && data.update.messages) {
               finalAnswer = data.update.messages[data.update.messages.length - 1].content
            }
          } else if (data.type === 'done') {
            if (currentProject.value) {
              currentProject.value.qa_pairs.push({
                question: query,
                answer: finalAnswer
              })
            }
            newQuestion.value = ''
            isLoading.value = false
          }
        }
      }
    }
  } catch (e) {
    ElMessage.error('分析失败')
    isLoading.value = false
  }
}

const generateFinalReport = async () => {
  if (!currentProject.value?.qa_pairs.length) return
  
  const query = `基于以下问答对生成一份完整的总结报告：\n\n` + 
                currentProject.value.qa_pairs.map((qa, i) => `Q${i+1}: ${qa.question}\nA${i+1}: ${qa.answer}`).join('\n\n')
  
  isLoading.value = true
  progressNodes.value = []
  
  try {
    const response = await fetch(`${apiClient.defaults.baseURL}/api/qa/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        kb_names: selectedKbs.value,
        history: currentProject.value.qa_pairs
      })
    })

    if (!response.body) return
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalReport = ''

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
            progressNodes.value.push({ node: data.node, msg: '生成报告中...' })
            if (data.node === 'QAWriter' && data.update.messages) {
               finalReport = data.update.messages[data.update.messages.length - 1].content
            }
          } else if (data.type === 'done') {
            if (currentProject.value) {
              currentProject.value.final_report = finalReport
            }
            isLoading.value = false
          }
        }
      }
    }
  } catch (e) {
    ElMessage.error('报告生成失败')
    isLoading.value = false
  }
}

onMounted(() => {
  fetchKbs()
})
</script>

<style scoped>
.qa-container {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

.qa-sidebar {
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
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.section-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
  text-transform: uppercase;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.history-item {
  padding: 10px;
  margin-bottom: 5px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s;
}

.history-item:hover {
  background: #f5f7fa;
}

.history-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.history-title {
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qa-main {
  flex: 1;
  overflow-y: auto;
  padding: 40px;
}

.entry-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 80%;
}

.entry-card {
  width: 500px;
}

.card-header h2 {
  margin: 0;
  margin-bottom: 8px;
}

.card-header p {
  margin: 0;
  color: #909399;
}

.project-dashboard {
  max-width: 900px;
  margin: 0 auto;
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
}

.header-left h2 {
  margin: 0;
  margin-bottom: 10px;
}

.qa-history {
  margin-bottom: 30px;
}

.qa-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
}

.qa-idx {
  font-weight: bold;
}

.qa-answer {
  padding: 15px;
  background: #f9f9f9;
  border-radius: 4px;
}

.new-question-area {
  margin-bottom: 30px;
  background: #fff;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.action-bar {
  margin-top: 15px;
  display: flex;
  gap: 15px;
}

.analysis-progress {
  margin-bottom: 30px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.progress-steps {
  margin-top: 15px;
}

.step-item {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}

.report-section {
  margin-bottom: 30px;
}

.report-card {
  background: #fff;
  padding: 20px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.6;
}
</style>
