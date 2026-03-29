<template>
  <div class="deep-read-container">
    <el-container>
      <!-- 左侧：历史记录与上传 -->
      <el-aside width="350px" class="history-aside">
        <div class="history-section">
          <div class="history-header">
            <h3>📜 历史报告</h3>
            <el-button type="primary" size="small" :icon="Plus" @click="showUpload = true">新分析</el-button>
          </div>
          
          <el-scrollbar max-height="calc(100vh - 100px)">
            <div 
              v-for="report in reportList" 
              :key="report.id" 
              class="history-item"
              :class="{ active: currentReportId === report.id }"
              @click="loadReport(report.id)"
            >
              <div class="item-title">{{ report.title }}</div>
              <div class="item-meta">
                <span>{{ report.source_name }}</span>
                <span>{{ formatDate(report.created_at) }}</span>
              </div>
              <el-button 
                class="delete-btn" 
                type="danger" 
                size="small" 
                :icon="Delete" 
                circle 
                @click.stop="handleDeleteReport(report.id)"
              />
            </div>
            <el-empty v-if="reportList.length === 0" description="暂无历史报告" />
          </el-scrollbar>
        </div>
      </el-aside>

      <!-- 中间：上传与进度 (仅在需要时显示) -->
      <el-aside v-if="showUpload || isAnalyzing" width="400px" class="upload-aside">
        <div class="upload-section">
          <div class="section-header">
            <h2>📚 深度解读</h2>
            <el-button v-if="!isAnalyzing" circle :icon="Close" size="small" @click="showUpload = false" />
          </div>
          
          <div v-if="!isAnalyzing">
            <p class="description">上传 PDF 文档或粘贴长文本，AI 将为您生成多维度的深度分析报告</p>
            
            <el-tabs v-model="inputMode" class="input-tabs">
              <el-tab-pane label="📁 文件上传" name="file">
                <el-upload
                  ref="uploadRef"
                  drag
                  :auto-upload="false"
                  :on-change="handleFileChange"
                  :limit="1"
                  accept=".pdf"
                  class="upload-area"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">拖拽 PDF 到此处或 <em>点击上传</em></div>
                </el-upload>
              </el-tab-pane>
              
              <el-tab-pane label="✍️ 文本粘贴" name="text">
                <el-input
                  v-model="pastedText"
                  type="textarea"
                  :rows="12"
                  placeholder="在此处粘贴您想分析的长文本内容..."
                />
              </el-tab-pane>
            </el-tabs>

            <div v-if="selectedFile || pastedText" class="action-section">
              <el-card shadow="never">
                <div v-if="inputMode === 'file' && selectedFile" class="file-detail">
                  <el-icon><Document /></el-icon>
                  <span>{{ selectedFile.name }}</span>
                </div>
                <div v-else-if="inputMode === 'text' && pastedText" class="text-detail">
                  <el-icon><Document /></el-icon>
                  <span>已粘贴 {{ pastedText.length }} 字</span>
                </div>
                <el-button
                  type="primary"
                  @click="startAnalysis"
                  :loading="isAnalyzing"
                  style="width: 100%; margin-top: 15px;"
                  :disabled="inputMode === 'text' && !pastedText.trim()"
                >
                  开始深度分析
                </el-button>
              </el-card>
            </div>
          </div>

          <div v-if="analysisProgress.length > 0" class="progress-section">
            <h3>🔍 分析流水线</h3>
            <el-timeline>
              <el-timeline-item
                v-for="(step, idx) in analysisProgress"
                :key="idx"
                :timestamp="step.time"
                placement="top"
                :type="step.status"
              >
                {{ step.message }}
              </el-timeline-item>
            </el-timeline>
          </div>
        </div>
      </el-aside>

      <!-- 右侧：报告展示 -->
      <el-main>
        <div v-if="!reportContent" class="empty-state">
          <el-empty description="请从左侧选择历史报告或点击「新分析」开始" />
        </div>
        
        <div v-else class="report-container">
          <div class="report-header">
            <div class="title-area">
              <h2>📖 {{ currentReportTitle || '分析报告' }}</h2>
            </div>
            <div class="actions">
              <el-button @click="exportReport" :icon="Download">导出 MD</el-button>
              <el-button @click="clearReport" :icon="Refresh">清空</el-button>
            </div>
          </div>
          
          <div class="report-content" ref="reportArea">
            <div
              class="markdown-body"
              v-html="renderMarkdown(reportContent)"
            ></div>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Document, Download, Refresh, Plus, Delete, Close } from '@element-plus/icons-vue'
import { marked } from 'marked'
import apiClient from '@/api'
import dayjs from 'dayjs'

const uploadRef = ref()
const inputMode = ref('file')
const pastedText = ref('')
const selectedFile = ref<File | null>(null)
const isAnalyzing = ref(false)
const showUpload = ref(false)
const analysisProgress = ref<any[]>([])
const reportContent = ref<string>('')
const currentReportId = ref<string | null>(null)
const currentReportTitle = ref<string>('')
const reportList = ref<any[]>([])
const reportArea = ref<HTMLElement | null>(null)
const DEEP_READ_SEED_KEY = 'reading-copilot:deep-read-seed'

// --- 生命周期 ---
onMounted(() => {
  fetchReports()
  hydrateFromCopilotSeed()
})

const hydrateFromCopilotSeed = () => {
  try {
    const raw = localStorage.getItem(DEEP_READ_SEED_KEY)
    if (!raw) return
    const seed = JSON.parse(raw)
    localStorage.removeItem(DEEP_READ_SEED_KEY)

    inputMode.value = 'text'
    pastedText.value = seed.text || ''
    currentReportTitle.value = seed.title || '来自长文伴读'
    showUpload.value = true

    if (pastedText.value) {
      ElMessage.success('已带入长文伴读内容，可以直接开始深度分析')
    }
  } catch (error) {
    console.error('读取长文伴读种子失败:', error)
  }
}

// --- 数据获取 ---
const fetchReports = async () => {
  try {
    const res: any = await apiClient.get('/api/read/reports')
    reportList.value = res.reports || []
  } catch (error) {
    console.error('获取报告列表失败:', error)
  }
}

const loadReport = async (id: string) => {
  try {
    const res: any = await apiClient.get(`/api/read/reports/${id}`)
    currentReportId.value = id
    currentReportTitle.value = res.title
    reportContent.value = res.content
    showUpload.value = false
  } catch (error) {
    ElMessage.error('加载报告失败')
  }
}

const handleDeleteReport = (id: string) => {
  ElMessageBox.confirm('确定要删除这份分析报告吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    await apiClient.delete(`/api/read/reports/${id}`)
    ElMessage.success('已删除')
    if (currentReportId.value === id) {
      currentReportId.value = null
      reportContent.value = ''
    }
    fetchReports()
  })
}

// --- 文件处理 ---
const handleFileChange = (file: any) => {
  if (file.raw && file.raw.type === 'application/pdf') {
    selectedFile.value = file.raw
  } else {
    ElMessage.error('请选择 PDF 文件')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
  }
}

const startAnalysis = async () => {
  if (inputMode.value === 'file' && !selectedFile.value) return ElMessage.warning('请先选择文件')
  if (inputMode.value === 'text' && !pastedText.value.trim()) return ElMessage.warning('请先输入文本')

  isAnalyzing.value = true
  analysisProgress.value = []
  reportContent.value = ''
  
  if (inputMode.value === 'file' && selectedFile.value) {
    currentReportTitle.value = selectedFile.value.name.replace('.pdf', '')
  } else {
    currentReportTitle.value = pastedText.value.trim().slice(0, 20) + '...'
  }

  const baseUrl = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000'

  try {
    if (inputMode.value === 'file' && selectedFile.value) {
      const formData = new FormData()
      formData.append('file', selectedFile.value)

      const uploadRes: any = await apiClient.post('/api/read/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      addProgressStep('文件上传成功，启动分析引擎...', 'success')
      const sseUrl = `${baseUrl}/api/read/analyze?file_path=${encodeURIComponent(uploadRes.temp_path)}&doc_title=${encodeURIComponent(currentReportTitle.value)}`
      setupEventSource(sseUrl)
    } else {
      addProgressStep('文本已就绪，启动分析引擎...', 'success')
      await startTextAnalysis(baseUrl)
    }
  } catch (error: any) {
    ElMessage.error(`分析失败：${error.message}`)
    isAnalyzing.value = false
  }
}

const setupEventSource = (url: string) => {
  const eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    handleAnalysisUpdate(data, eventSource)
  }

  eventSource.onerror = (err) => {
    console.error('SSE Error:', err)
    eventSource.close()
    isAnalyzing.value = false
    ElMessage.error('分析过程中断')
  }
}

const startTextAnalysis = async (baseUrl: string) => {
  try {
    const formData = new FormData()
    formData.append('text', pastedText.value)
    formData.append('doc_title', currentReportTitle.value)

    const response = await fetch(`${baseUrl}/api/read/analyze_text`, {
      method: 'POST',
      body: formData
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) throw new Error('无法创建读取流')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          handleAnalysisUpdate(data)
        }
      }
    }
  } catch (error: any) {
    ElMessage.error(`分析失败：${error.message}`)
    isAnalyzing.value = false
  }
}

const handleAnalysisUpdate = (data: any, eventSource?: EventSource) => {
  if (data.type === 'progress') {
    addProgressStep(data.message, 'primary')
    if (data.report_preview) {
      reportContent.value = data.report_preview
    }
  } else if (data.type === 'done') {
    if (eventSource) eventSource.close()
    isAnalyzing.value = false
    addProgressStep('分析完成！已保存至历史记录', 'success')
    fetchReports()
    setTimeout(() => {
      if (reportList.value.length > 0) loadReport(reportList.value[0].id)
    }, 500)
  } else if (data.type === 'error') {
    if (eventSource) eventSource.close()
    isAnalyzing.value = false
    ElMessage.error(`分析失败：${data.message}`)
  }
}

// --- 辅助功能 ---
const addProgressStep = (message: string, status: string) => {
  analysisProgress.value.push({
    message,
    status,
    time: dayjs().format('HH:mm:ss')
  })
  nextTick(() => {
    const el = document.querySelector('.progress-section .el-timeline')
    if (el) el.scrollTop = el.scrollHeight
  })
}

const renderMarkdown = (text: string) => marked(text, { breaks: true, gfm: true })

const formatDate = (date: string) => dayjs(date).format('MM-DD HH:mm')

const exportReport = () => {
  const blob = new Blob([reportContent.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${currentReportTitle.value}_分析报告.md`
  a.click()
  URL.revokeObjectURL(url)
}

const clearReport = () => {
  reportContent.value = ''
  currentReportId.value = null
  currentReportTitle.value = ''
}
</script>

<style scoped>
.deep-read-container {
  height: 100vh;
  background: #f0f2f5;
}

.history-aside {
  background: #fff;
  border-right: 1px solid #dcdfe6;
}

.history-section {
  padding: 15px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.history-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: all 0.3s;
  position: relative;
  border: 1px solid transparent;
}

.history-item:hover {
  background: #f5f7fa;
}

.history-item.active {
  background: #ecf5ff;
  border-color: #409eff;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 25px;
}

.item-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  display: flex;
  justify-content: space-between;
}

.delete-btn {
  position: absolute;
  right: 8px;
  top: 12px;
  opacity: 0;
  transition: opacity 0.3s;
}

.history-item:hover .delete-btn {
  opacity: 1;
}

.upload-aside {
  background: #fff;
  border-right: 1px solid #dcdfe6;
  box-shadow: 2px 0 8px rgba(0,0,0,0.05);
  z-index: 10;
}

.upload-section {
  padding: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.description {
  color: #606266;
  font-size: 13px;
  margin-bottom: 20px;
  line-height: 1.6;
}

.file-info {
  margin-top: 20px;
}

.file-detail {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  word-break: break-all;
}

.progress-section {
  margin-top: 30px;
  max-height: 400px;
  overflow-y: auto;
}

.progress-section h3 {
  font-size: 15px;
  margin-bottom: 15px;
  color: #303133;
}

.report-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.report-header {
  padding: 15px 25px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
}

.report-content {
  flex: 1;
  overflow-y: auto;
  padding: 40px;
  background: #fafafa;
}

.markdown-body {
  max-width: 850px;
  margin: 0 auto;
  padding: 40px;
  background: #fff;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
  border-radius: 4px;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
