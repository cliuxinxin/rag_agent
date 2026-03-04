<template>
  <div class="deep-write-container">
    <el-container>
      <!-- 左侧：写作向导 -->
      <el-aside width="450px">
        <div class="wizard-section">
          <h2>✍️ 深度写作</h2>
          
          <el-steps direction="vertical" :active="currentStep" finish-status="success">
            <el-step title="选择主题" description="确定写作主题和类型" />
            <el-step title="编辑大纲" description="构建文章结构框架" />
            <el-step title="生成内容" description="AI 辅助创作内容" />
            <el-step title="完善优化" description="润色和优化文章" />
          </el-steps>

          <div class="step-content" style="margin-top: 30px;">
            <!-- Step 1: 选择主题 -->
            <div v-if="currentStep === 0" class="step-panel">
              <el-form :model="writeForm" label-width="100px">
                <el-form-item label="文章主题" required>
                  <el-input
                    v-model="writeForm.topic"
                    placeholder="请输入文章主题"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="文章类型" required>
                  <el-select v-model="writeForm.type" placeholder="请选择文章类型" style="width: 100%">
                    <el-option label="技术文章" value="tech" />
                    <el-option label="产品文档" value="product" />
                    <el-option label="营销文案" value="marketing" />
                    <el-option label="学术论文" value="academic" />
                    <el-option label="其他" value="other" />
                  </el-select>
                </el-form-item>
                <el-form-item label="字数要求" required>
                  <el-input-number
                    v-model="writeForm.wordCount"
                    :min="500"
                    :max="10000"
                    :step="500"
                  />
                </el-form-item>
              </el-form>
            </div>

            <!-- Step 2: 编辑大纲 -->
            <div v-if="currentStep === 1" class="step-panel">
              <el-form :model="writeForm" label-width="100px">
                <el-form-item label="章节大纲" required>
                  <el-input
                    v-model="writeForm.outline"
                    type="textarea"
                    :rows="12"
                    placeholder="请输入文章大纲，每行一个章节"
                  />
                </el-form-item>
              </el-form>
            </div>

            <!-- Step 3 & 4: 生成内容和优化 -->
            <div v-if="currentStep >= 2" class="step-panel">
              <div class="generation-status">
                <el-progress
                  :percentage="generationProgress"
                  :status="generationStatus"
                />
                <p class="status-text">{{ statusText }}</p>
              </div>

              <div v-if="generationLog.length > 0" class="log-section">
                <h4>生成日志</h4>
                <el-timeline>
                  <el-timeline-item
                    v-for="(log, idx) in generationLog"
                    :key="idx"
                    :timestamp="log.time"
                    placement="top"
                    :type="log.status"
                  >
                    {{ log.message }}
                  </el-timeline-item>
                </el-timeline>
              </div>
            </div>
          </div>

          <div class="navigation-buttons">
            <el-button @click="prevStep" :disabled="currentStep === 0">
              上一步
            </el-button>
            <el-button
              v-if="currentStep < 3"
              type="primary"
              @click="nextStep"
              :loading="isGenerating && currentStep >= 2"
            >
              {{ currentStep === 2 ? '开始生成' : '下一步' }}
            </el-button>
            <el-button
              v-else
              type="success"
              @click="finishWriting"
              :loading="isGenerating"
            >
              完成写作
            </el-button>
          </div>
        </div>
      </el-aside>

      <!-- 右侧：实时预览 -->
      <el-main>
        <div v-if="!articleContent" class="empty-state">
          <el-empty description="请按照向导步骤开始写作" />
        </div>

        <div v-else class="preview-section">
          <div class="preview-header">
            <h2>📝 {{ writeForm.topic }}</h2>
            <div class="actions">
              <el-button @click="exportArticle" :icon="Download">导出</el-button>
              <el-button @click="saveDraft" :icon="Save">保存草稿</el-button>
            </div>
          </div>

          <div class="article-content">
            <div
              class="markdown-body"
              v-html="renderMarkdown(articleContent)"
            ></div>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Save } from '@element-plus/icons-vue'
import { marked } from 'marked'

const currentStep = ref(0)
const isGenerating = ref(false)
const generationProgress = ref(0)
const generationStatus = ref<'success' | 'exception'>('success')
const generationLog = ref<any[]>([])

const writeForm = ref({
  topic: '',
  type: 'tech',
  wordCount: 2000,
  outline: ''
})

const articleContent = ref('')

const statusText = computed(() => {
  if (generationProgress.value < 30) return '正在分析主题...'
  if (generationProgress.value < 60) return '正在收集资料...'
  if (generationProgress.value < 80) return '正在撰写内容...'
  if (generationProgress.value < 100) return '正在优化润色...'
  return '生成完成！'
})

// Markdown 渲染配置
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderMarkdown = (text: string) => {
  return marked(text)
}

const addLog = (message: string, status: 'primary' | 'success' | 'warning' | 'danger' | 'info') => {
  generationLog.value.push({
    message,
    status,
    time: new Date().toLocaleTimeString(),
  })
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const nextStep = async () => {
  if (currentStep.value === 0) {
    // 验证主题
    if (!writeForm.value.topic) {
      ElMessage.warning('请输入文章主题')
      return
    }
    // 自动生成大纲
    await generateOutline()
  } else if (currentStep.value === 1) {
    // 验证大纲
    if (!writeForm.value.outline) {
      ElMessage.warning('请输入文章大纲')
      return
    }
  } else if (currentStep.value === 2) {
    // 开始生成内容
    await generateContent()
  }
  
  if (currentStep.value < 3) {
    currentStep.value++
  }
}

const generateOutline = async () => {
  isGenerating.value = true
  addLog('正在分析主题...', 'primary')
  
  try {
    // 模拟 AI 生成大纲
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    const autoOutline = generateAutoOutline(writeForm.value.topic)
    writeForm.value.outline = autoOutline
    
    addLog('大纲生成完成', 'success')
    isGenerating.value = false
    ElMessage.success('已自动生成大纲')
  } catch (error) {
    console.error('生成大纲失败:', error)
    ElMessage.error('生成大纲失败')
    isGenerating.value = false
  }
}

const generateAutoOutline = (topic: string): string => {
  // 简单的模板生成，实际应该调用后端 API
  return `# ${topic}\n\n## 引言\n## 背景介绍\n## 核心内容\n## 实践应用\n## 总结与展望`
}

const generateContent = async () => {
  isGenerating.value = true
  generationProgress.value = 0
  
  try {
    // 模拟分阶段生成
    const chapters = writeForm.value.outline.split('\n').filter(line => line.trim())
    const totalChapters = chapters.length
    
    for (let i = 0; i < totalChapters; i++) {
      const chapter = chapters[i]
      addLog(`正在生成：${chapter}`, 'primary')
      
      // 模拟生成每个章节
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      articleContent.value += `\n\n## ${chapter.replace('# ', '')}\n\n这里是 ${chapter} 的详细内容...`
      
      generationProgress.value = Math.round(((i + 1) / totalChapters) * 100)
      addLog(`${chapter} 生成完成`, 'success')
    }
    
    generationStatus.value = 'success'
    addLog('文章生成完成！', 'success')
    isGenerating.value = false
    
  } catch (error) {
    console.error('生成失败:', error)
    generationStatus.value = 'exception'
    addLog('生成失败，请重试', 'danger')
    isGenerating.value = false
  }
}

const finishWriting = () => {
  ElMessage.success('写作完成！文章已保存')
}

const exportArticle = () => {
  const blob = new Blob([articleContent.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${writeForm.value.topic}.md`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

const saveDraft = () => {
  // TODO: 保存到本地或服务器
  ElMessage.success('草稿已保存')
}
</script>

<style scoped>
.deep-write-container {
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

.wizard-section {
  padding: 20px;
}

.step-panel {
  min-height: 300px;
}

.generation-status {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.status-text {
  margin-top: 10px;
  color: #606266;
  font-size: 14px;
}

.log-section {
  margin-top: 20px;
  max-height: 300px;
  overflow-y: auto;
}

.navigation-buttons {
  margin-top: 20px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
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

.article-content {
  flex: 1;
  overflow-y: auto;
  padding: 30px;
}

.markdown-body {
  max-width: 900px;
  margin: 0 auto;
  line-height: 1.8;
}
</style>
