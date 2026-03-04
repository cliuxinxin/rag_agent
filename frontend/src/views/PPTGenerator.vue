<template>
  <div class="ppt-container">
    <el-container>
      <!-- 左侧：大纲编辑 -->
      <el-aside width="500px">
        <div class="editor-section">
          <h2>📊 PPT 生成</h2>
          <p class="description">输入主题和大纲，AI 将为您生成精美的 PPT</p>

          <el-form :model="pptForm" label-width="100px">
            <el-form-item label="PPT 主题" required>
              <el-input
                v-model="pptForm.topic"
                placeholder="请输入 PPT 主题"
                clearable
              />
            </el-form-item>

            <el-form-item label="页数" required>
              <el-input-number
                v-model="pptForm.slideCount"
                :min="5"
                :max="50"
                :step="1"
              />
            </el-form-item>

            <el-form-item label="大纲内容" required>
              <el-input
                v-model="pptForm.outline"
                type="textarea"
                :rows="15"
                placeholder="请输入 PPT 大纲，每行一个章节标题"
              />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="generatePPT"
                :loading="generating"
                style="width: 100%"
              >
                {{ generating ? '生成中...' : '生成 PPT' }}
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="generationProgress.length > 0" class="progress-section">
            <h3>生成进度</h3>
            <el-timeline>
              <el-timeline-item
                v-for="(step, idx) in generationProgress"
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

      <!-- 右侧：预览区域 -->
      <el-main>
        <div v-if="!pptGenerated" class="empty-state">
          <el-empty description="请填写大纲并点击生成 PPT" />
        </div>

        <div v-else class="preview-section">
          <div class="preview-header">
            <h2>📋 PPT 预览</h2>
            <div class="actions">
              <el-button @click="downloadPPT" :icon="Download" type="primary">
                下载 PPT
              </el-button>
              <el-button @click="resetPPT" :icon="Refresh">
                重新生成
              </el-button>
            </div>
          </div>

          <div class="slides-preview">
            <div
              v-for="(slide, idx) in slides"
              :key="idx"
              class="slide-card"
              :class="{ active: currentSlide === idx }"
              @click="currentSlide = idx"
            >
              <div class="slide-number">{{ idx + 1 }}</div>
              <div class="slide-content">
                <h3>{{ slide.title }}</h3>
                <ul>
                  <li v-for="(point, pIdx) in slide.points" :key="pIdx">
                    {{ point }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import apiClient from '@/api'

const pptForm = ref({
  topic: '',
  outline: '',
  slideCount: 10
})

const generating = ref(false)
const pptGenerated = ref(false)
const generationProgress = ref<any[]>([])
const currentSlide = ref(0)
const slides = ref<any[]>([])

const addProgressStep = (message: string, status: 'primary' | 'success' | 'warning' | 'danger') => {
  generationProgress.value.push({
    message,
    status,
    time: new Date().toLocaleTimeString(),
  })
}

const generatePPT = async () => {
  if (!pptForm.value.topic || !pptForm.value.outline) {
    ElMessage.warning('请填写完整信息')
    return
  }

  generating.value = true
  generationProgress.value = []
  pptGenerated.value = false

  try {
    // 解析大纲
    const outlineItems = pptForm.value.outline.split('\n').filter(line => line.trim())
    
    addProgressStep('开始生成 PPT...', 'primary')

    // 调用 API 生成 PPT
    const response = await apiClient.post('/api/ppt/generate', {
      topic: pptForm.value.topic,
      outline: outlineItems,
      slide_count: pptForm.value.slideCount
    })

    addProgressStep('大纲分析完成', 'success')
    addProgressStep('正在生成幻灯片...', 'primary')

    // 模拟生成过程
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    addProgressStep('内容优化完成', 'success')
    addProgressStep('样式美化完成', 'success')
    addProgressStep('PPT 生成成功！', 'success')

    // 生成预览数据（实际应该从后端返回）
    slides.value = outlineItems.map((item, idx) => ({
      title: item,
      points: [
        `要点 1 for ${item}`,
        `要点 2 for ${item}`,
        `要点 3 for ${item}`
      ]
    }))

    pptGenerated.value = true
    generating.value = false

  } catch (error: any) {
    console.error('生成失败:', error)
    ElMessage.error(`生成失败：${error.message}`)
    addProgressStep(`错误：${error.message}`, 'danger')
    generating.value = false
  }
}

const downloadPPT = async () => {
  try {
    const response = await apiClient.post('/api/ppt/generate', {
      topic: pptForm.value.topic,
      outline: pptForm.value.outline.split('\n').filter(line => line.trim()),
      slide_count: pptForm.value.slideCount
    }, {
      responseType: 'blob'
    })

    const blob = new Blob([response], {
      type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${pptForm.value.topic}.pptx`
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success('下载成功')
  } catch (error: any) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

const resetPPT = () => {
  pptGenerated.value = false
  generationProgress.value = []
  slides.value = []
  currentSlide.value = 0
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
  font-size: 14px;
  margin-bottom: 20px;
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
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-section {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.preview-header {
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

.slides-preview {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.slide-card {
  background: #fff;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s;
}

.slide-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.2);
}

.slide-card.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.slide-number {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #409eff;
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.slide-content h3 {
  margin-bottom: 15px;
  font-size: 16px;
  color: #303133;
}

.slide-content ul {
  list-style: none;
  padding: 0;
}

.slide-content li {
  padding: 5px 0;
  color: #606266;
  font-size: 14px;
}

.slide-content li::before {
  content: "•";
  color: #409eff;
  font-weight: bold;
  margin-right: 8px;
}
</style>
