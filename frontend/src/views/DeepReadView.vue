<template>
  <div class="deep-read-container">
    <el-container>
      <!-- 侧边栏：上传区域 -->
      <el-aside width="400px">
        <div class="upload-section">
          <h2>📚 深度阅读</h2>
          <p class="description">上传 PDF 文档，AI 将为您生成深度分析报告</p>
          
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
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只支持 pdf 文件
              </div>
            </template>
          </el-upload>

          <div v-if="selectedFile" class="file-info">
            <el-card>
              <div class="file-detail">
                <el-icon><Document /></el-icon>
                <span>{{ selectedFile.name }}</span>
              </div>
              <div class="file-size">
                {{ (selectedFile.size / 1024).toFixed(2) }} KB
              </div>
              <el-button
                type="primary"
                size="small"
                @click="startAnalysis"
                :loading="isAnalyzing"
                style="width: 100%; margin-top: 15px;"
              >
                {{ isAnalyzing ? '分析中...' : '开始分析' }}
              </el-button>
            </el-card>
          </div>

          <div v-if="analysisProgress.length > 0" class="progress-section">
            <h3>分析进度</h3>
            <el-timeline>
              <el-timeline-item
                v-for="(step, idx) in analysisProgress"
                :key="idx"
                :timestamp="step.time"
                placement="top"
                :type="step.status"
              >
                <el-card>
                  <p>{{ step.message }}</p>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
        </div>
      </el-aside>

      <!-- 主内容区：报告展示 -->
      <el-main>
        <div v-if="!reportContent" class="empty-state">
          <el-empty description="请上传 PDF 文档开始分析" />
        </div>
        
        <div v-else class="report-container">
          <div class="report-header">
            <h2>📖 分析报告</h2>
            <div class="actions">
              <el-button @click="exportReport" :icon="Download">导出</el-button>
              <el-button @click="clearReport" :icon="Refresh">重新分析</el-button>
            </div>
          </div>
          
          <div class="report-content">
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
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Download, Refresh } from '@element-plus/icons-vue'
import { marked } from 'marked'
import apiClient from '@/api'

const uploadRef = ref()
const selectedFile = ref<File | null>(null)
const isAnalyzing = ref(false)
const analysisProgress = ref<any[]>([])
const reportContent = ref<string>('')

// Markdown 渲染配置
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderMarkdown = (text: string) => {
  return marked(text)
}

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
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  isAnalyzing.value = true
  analysisProgress.value = []
  reportContent.value = ''

  try {
    // 1. 上传文件
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const uploadResponse = await apiClient.post('/api/read/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })

    addProgressStep('文件上传成功', 'success')

    // 2. 分析文档 (SSE 流式)
    addProgressStep('开始分析文档...', 'primary')

    const { fetchEventSource } = await import('@microsoft/fetch-event-source')
    
    await fetchEventSource(`${apiClient.defaults.baseURL}/api/read/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: `file_path=${encodeURIComponent(uploadResponse.temp_path)}&query=请分析这份文档`,
      onmessage: (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'progress') {
            addProgressStep(data.message, 'primary')
          } else if (data.type === 'done') {
            reportContent.value = data.result || '# 分析完成\n\n文档分析已完成。'
            isAnalyzing.value = false
            addProgressStep('分析完成！', 'success')
          } else if (data.type === 'error') {
            throw new Error(data.message)
          }
        } catch (e) {
          console.error('解析事件失败:', e)
        }
      },
      onerror: (error) => {
        console.error('SSE 错误:', error)
        throw error
      },
      onclose: () => {
        console.log('连接关闭')
      },
    })

  } catch (error: any) {
    console.error('分析失败:', error)
    ElMessage.error(`分析失败：${error.message}`)
    addProgressStep(`错误：${error.message}`, 'danger')
    isAnalyzing.value = false
  }
}

const addProgressStep = (message: string, status: 'primary' | 'success' | 'warning' | 'danger' | 'info') => {
  analysisProgress.value.push({
    message,
    status,
    time: new Date().toLocaleTimeString(),
  })
}

const exportReport = () => {
  const blob = new Blob([reportContent.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `分析报告_${new Date().getTime()}.md`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('报告已导出')
}

const clearReport = () => {
  reportContent.value = ''
  analysisProgress.value = []
  selectedFile.value = null
  uploadRef.value?.clearFiles()
}
</script>

<style scoped>
.deep-read-container {
  height: 100vh;
  background: #f5f7fa;
}

.el-container {
  height: 100%;
}

.el-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  overflow-y: auto;
}

.upload-section {
  padding: 20px;
}

.description {
  color: #606266;
  font-size: 14px;
  margin-bottom: 20px;
}

.upload-area {
  width: 100%;
}

.file-info {
  margin-top: 20px;
}

.file-detail {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: bold;
}

.file-size {
  color: #909399;
  font-size: 12px;
  margin-top: 5px;
}

.progress-section {
  margin-top: 30px;
}

.progress-section h3 {
  margin-bottom: 15px;
  font-size: 16px;
}

.el-main {
  background: #fff;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.report-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.report-header {
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
}

.actions {
  display: flex;
  gap: 10px;
}

.report-content {
  flex: 1;
  overflow-y: auto;
  padding: 30px;
}

.markdown-body {
  max-width: 900px;
  margin: 0 auto;
  line-height: 1.8;
}

/* Markdown 样式优化 */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-body :deep(p) {
  margin-bottom: 16px;
}

.markdown-body :deep(code) {
  background: #f6f8fa;
  padding: 3px 6px;
  border-radius: 6px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.markdown-body :deep(pre) {
  background: #f6f8fa;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin-bottom: 16px;
}
</style>
