<template>
  <div class="ppt-container">
    <el-container>
      <!-- 左侧：生成配置 -->
      <el-aside width="450px">
        <div class="editor-section">
          <h2>📊 PPT 深度生成</h2>
          <p class="description">输入主题和素材，AI 将为您策划大纲并撰写每页幻灯片内容</p>

          <el-form :model="pptForm" label-position="top">
            <el-form-item label="PPT 主题" required>
              <el-input v-model="pptForm.topic" placeholder="例如：2024 AI 趋势分析" clearable />
            </el-form-item>

            <el-form-item label="📁 导入素材">
              <el-upload
                class="upload-demo"
                drag
                action=""
                :auto-upload="false"
                :on-change="handleFileChange"
                :limit="1"
                :file-list="fileList"
              >
                <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                <div class="el-upload__text">
                  拖拽文件或 <em>点击上传</em> (PDF/TXT)
                </div>
              </el-upload>
            </el-form-item>

            <el-form-item label="核心内容/素材" required>
              <el-input
                v-model="pptForm.content"
                type="textarea"
                :rows="8"
                placeholder="请输入详细的参考内容，或通过上方上传提取..."
              />
            </el-form-item>

            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="预期页数">
                  <el-input-number v-model="pptForm.slideCount" :min="5" :max="30" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="操作">
                  <el-button
                    type="primary"
                    @click="startPPTGeneration"
                    :loading="generating"
                    style="width: 100%"
                  >
                    开始生成
                  </el-button>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>

          <div v-if="runLogs.length > 0" class="progress-section">
            <h3>🚀 生成流水线</h3>
            <div class="log-container" ref="logScroll">
              <div v-for="(log, idx) in runLogs" :key="idx" class="log-item">
                {{ log }}
              </div>
            </div>
          </div>
        </div>
      </el-aside>

      <!-- 右侧：状态展示与下载 -->
      <el-main>
        <div v-if="!pptGenerated && !generating" class="empty-state">
          <el-empty description="配置左侧信息以开始生成" />
        </div>

        <div v-else-if="generating" class="generating-state">
          <el-result icon="info" title="正在生成中" sub-title="AI 正在策划大纲并撰写内容，请稍候...">
            <template #extra>
              <el-progress type="circle" :percentage="progress" />
            </template>
          </el-result>
        </div>

        <div v-else class="preview-section">
          <el-result icon="success" title="生成完成" :sub-title="`已为您准备好 ${pptForm.topic} 的 PPT 文件` ">
            <template #extra>
              <el-button type="primary" size="large" @click="downloadPPT" :icon="Download">立即下载 PPTX</el-button>
              <el-button @click="resetPPT" :icon="Refresh">重新生成</el-button>
            </template>
          </el-result>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh, UploadFilled } from '@element-plus/icons-vue'
import apiClient from '@/api'

const pptForm = ref({
  topic: '',
  content: '',
  slideCount: 10
})

const fileList = ref<any[]>([])
const generating = ref(false)
const pptGenerated = ref(false)
const runLogs = ref<string[]>([])
const progress = ref(0)
const projectId = ref('')
const logScroll = ref<HTMLElement | null>(null)

const handleFileChange = async (file: any) => {
  const formData = new FormData()
  formData.append('file', file.raw)
  try {
    const res: any = await apiClient.post('/api/write/extract_text', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    pptForm.value.content = res.text
    ElMessage.success('文本提取成功')
  } catch (error) {
    ElMessage.error('文件解析失败')
  }
}

const startPPTGeneration = async () => {
  if (!pptForm.value.topic || !pptForm.value.content) {
    return ElMessage.warning('请填写主题和内容')
  }

  generating.value = true
  pptGenerated.value = false
  runLogs.value = ['📡 正在连接生成服务器...']
  progress.value = 5
  projectId.value = ''

  try {
    const response = await fetch(`${apiClient.defaults.baseURL}/api/ppt/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: pptForm.value.topic,
        content: pptForm.value.content,
        slide_count: pptForm.value.slideCount
      })
    })

    if (!response.body) throw new Error('No response body')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          handleSSE(data)
        }
      }
    }
  } catch (error: any) {
    ElMessage.error(`生成失败: ${error.message}`)
    generating.value = false
  }
}

const handleSSE = (data: any) => {
  if (data.logs) {
    runLogs.value.push(...data.logs)
    scrollToBottom()
  }

  if (data.node === 'Planner') progress.value = 30
  if (data.node === 'Writer') progress.value = 70
  if (data.node === 'Renderer') progress.value = 95
  
  if (data.node === 'FINISH') {
    projectId.value = data.project_id
    progress.value = 100
    generating.value = false
    pptGenerated.value = true
    ElMessage.success('PPT 生成成功！')
  }

  if (data.node === 'ERROR') {
    ElMessage.error(data.detail)
    generating.value = false
  }
}

const downloadPPT = () => {
  if (!projectId.value) return
  window.location.href = `${apiClient.defaults.baseURL}/api/ppt/download/${projectId.value}`
}

const resetPPT = () => {
  pptGenerated.value = false
  runLogs.value = []
  progress.value = 0
}

const scrollToBottom = () => {
  nextTick(() => {
    if (logScroll.value) {
      logScroll.value.scrollTop = logScroll.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.ppt-container {
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

.editor-section {
  padding: 20px;
}

.description {
  color: #606266;
  font-size: 13px;
  margin-bottom: 20px;
  line-height: 1.6;
}

.progress-section {
  margin-top: 25px;
}

.log-container {
  height: 300px;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 8px;
  font-family: monospace;
  font-size: 12px;
  overflow-y: auto;
}

.log-item {
  margin-bottom: 6px;
  line-height: 1.4;
}

.el-main {
  background: #fff;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-section, .generating-state {
  width: 100%;
  max-width: 600px;
}
</style>
