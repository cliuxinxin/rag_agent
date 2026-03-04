<template>
  <div class="deep-write-container">
    <el-container>
      <!-- 左侧：历史记录 -->
      <el-aside width="300px" class="history-aside">
        <div class="history-section">
          <div class="history-header">
            <h3>📜 项目历史</h3>
            <el-button type="primary" size="small" :icon="Plus" @click="startNewProject">开启新策划</el-button>
          </div>
          <el-scrollbar max-height="calc(100vh - 100px)">
            <div 
              v-for="p in projectList" 
              :key="p.id" 
              class="history-item"
              :class="{ active: projectId === p.id }"
              @click="loadProject(p.id)"
            >
              <div class="item-title">{{ p.title }}</div>
              <div class="item-meta">{{ formatDate(p.updated_at) }}</div>
              <el-button class="del-btn" type="text" :icon="Delete" @click.stop="handleDeleteProject(p.id)" />
            </div>
            <el-empty v-if="!projectList.length" description="暂无历史" image-size="60" />
          </el-scrollbar>
        </div>
      </el-aside>

      <!-- 中间：核心操作区 (Wizard) -->
      <el-aside width="500px" class="wizard-aside">
        <div class="wizard-content">
          <div class="wizard-header">
            <h2>📰 新闻工作室</h2>
            <el-progress :percentage="progressPercentage" :status="progressStatus" />
            <div class="step-label">当前阶段：{{ stepLabels[currentStep] }}</div>
          </div>
          <!-- Step 0: 素材与配置 -->
          <div v-if="currentStep === 0" class="step-panel">
            <el-form :model="writeForm" label-position="top">
              <el-form-item label="素材导入">
                <el-tabs v-model="inputTab" class="tight-tabs">
                  <el-tab-pane label="📁 上传文档" name="file">
                    <el-upload
                      drag
                      action=""
                      :auto-upload="false"
                      :on-change="handleFileChange"
                      :limit="1"
                      :show-file-list="true"
                    >
                      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                      <div class="el-upload__text">PDF / TXT</div>
                    </el-upload>
                  </el-tab-pane>
                  <el-tab-pane label="📝 粘贴文本" name="text">
                    <el-input v-model="writeForm.source_text" type="textarea" :rows="4" placeholder="在此粘贴..." />
                  </el-tab-pane>
                </el-tabs>
              </el-form-item>
          
              <el-row :gutter="10">
                <el-col :span="12">
                  <el-form-item label="🎭 身份与语调">
                    <el-select v-model="writeForm.style_tone">
                      <el-option value="犀利独到 (资深主编)" label="犀利独到 (资深主编)" />
                      <el-option value="客观中立 (分析师)" label="客观中立 (分析师)" />
                      <el-option value="深度专业 (技术专家)" label="深度专业 (技术专家)" />
                      <el-option value="通俗易懂 (科普博主)" label="通俗易懂 (科普博主)" />
                      <el-option value="正式公文 (报告风格)" label="正式公文 (报告风格)" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="📏 预估篇幅">
                    <el-select v-model="writeForm.article_length">
                      <el-option value="短讯 (500 字)" label="短讯 (500 字)" />
                      <el-option value="标准 (1500 字)" label="标准 (1500 字)" />
                      <el-option value="深度长文 (3000 字+)" label="深度长文 (3000 字+)" />
                      <el-option value="超长调研 (5000 字+)" label="超长调研 (5000 字+)" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
          
              <el-form-item label="📝 核心指令 / 必须包含的要素">
                <el-input v-model="writeForm.must_haves" type="textarea" :rows="2" placeholder="例：必须包含成本优势对比..." />
              </el-form-item>
          
              <div class="switches">
                <el-checkbox v-model="writeForm.enable_web_search" label="🌍 开启联网事实核查" border />
                <el-checkbox v-model="writeForm.auto_mode" label="⚡ 一键成文 (自动选角度 + 写作)" border />
              </div>
          
              <el-button type="primary" class="action-btn" :loading="isGenerating" @click="handlePlan">
                🚀 启动策划会
              </el-button>
            </el-form>
          </div>

          <!-- Step 1: 选题定调 -->
          <div v-else-if="currentStep === 1" class="step-panel">
            <div class="panel-desc">首席策划为您构思了以下切入角度：</div>
            <div class="angle-list">
              <el-card 
                v-for="(angle, idx) in generatedAngles" 
                :key="idx" 
                class="angle-card" 
                shadow="hover"
                @click="selectAngle(angle)"
              >
                <h4>{{ angle.title }}</h4>
                <p class="desc">{{ angle.desc }}</p>
                <div class="reason">💡 {{ angle.reasoning }}</div>
                <el-button type="primary" link class="select-btn">选择此角度</el-button>
              </el-card>
            </div>
          </div>

          <!-- Step 2: 大纲确认 -->
          <div v-else-if="currentStep === 2" class="step-panel">
            <div class="panel-desc">🏗️ 架构师已绘制蓝图，请检查：</div>
            <div class="outline-box">
              <div v-for="(sec, idx) in outline" :key="idx" class="outline-item">
                <span class="idx">{{ idx + 1 }}.</span>
                <div class="content">
                  <div class="title">{{ sec.title }}</div>
                  <div class="gist">{{ sec.gist }}</div>
                </div>
              </div>
            </div>
            
            <div class="refine-area">
              <el-input v-model="outlineFeedback" placeholder="💬 给架构师的修改指令 (例：删掉第 3 章...)" />
              <el-button type="warning" plain :loading="isGenerating" @click="handleRefineOutline">🔄 执行修改</el-button>
            </div>

            <el-divider />
            <el-button type="primary" class="action-btn" :loading="isGenerating" @click="startDrafting">
              ✅ 锁定大纲，开始写作
            </el-button>
          </div>

          <!-- Step 3: 写作日志 (运行中) -->
          <div v-else-if="currentStep === 3" class="step-panel">
            <div class="status-box">
              <el-alert title="🚀 新闻工作室正在全速运转..." type="info" :closable="false" show-icon />
              <div class="log-window" ref="logContainer">
                <div v-for="(log, i) in runLogs" :key="i" class="log-line">&gt; {{ log }}</div>
              </div>
            </div>
          </div>
        </div>
      </el-aside>

      <!-- 右侧：预览与最终结果 -->
      <el-main class="preview-main">
        <div v-if="!finalArticle && !draftingContent" class="empty-state">
          <el-empty description="作品将在这里呈现" />
        </div>
        
        <div v-else class="result-area">
          <el-tabs v-model="activePreviewTab">
            <!-- 1. 文字稿件 -->
            <el-tab-pane label="📄 文字稿件" name="text">
              <div class="article-wrapper">
                <el-collapse v-if="critiqueNotes" style="margin-bottom: 20px;">
                  <el-collapse-item title="🧐 主编审阅意见 (Reviewer Notes)" name="1">
                    <el-alert :title="critiqueNotes" type="warning" :closable="false" show-icon />
                  </el-collapse-item>
                </el-collapse>

                <!-- 标题与正文 -->
                <div class="markdown-body" v-html="renderedContent"></div>
                
                <!-- 写作光标效果 -->
                <div v-if="isGenerating && currentStep === 3" class="typing-cursor"></div>
              </div>
              
              <!-- 底部操作栏 -->
              <div class="bottom-actions" v-if="currentStep === 3 && !isGenerating">
                <el-button type="success" :icon="Check" @click="saveProject">💾 保存/更新归档</el-button>
                <el-button :icon="RefreshRight" @click="rePolish">🔄 重新润色</el-button>
                <el-button :icon="Back" @click="startNewProject">🔙 退出/重置</el-button>
              </div>
            </el-tab-pane>

            <!-- 2. 知识卡片 -->
            <el-tab-pane label="🖼️ 知识卡片" name="card">
              <KnowledgeCard 
                :title="selectedAngle?.title || '深度写作'" 
                :content="finalArticle || draftingContent" 
                source-tag="DeepSeek Newsroom" 
              />
            </el-tab-pane>

            <!-- 3. X (Twitter) -->
            <el-tab-pane label="🐦 X (Twitter)" name="twitter">
              <div class="twitter-tool">
                <div class="tool-desc">
                  <p>拒绝手动粘贴！选择模式生成推特文案。</p>
                </div>
                <el-radio-group v-model="twitterMode" class="mb-4">
                  <el-radio label="thread">🧵 Thread 模式 (配合 Typefully)</el-radio>
                  <el-radio label="long">💎 蓝 V 长推模式</el-radio>
                </el-radio-group>
                
                <el-button type="primary" :loading="isGeneratingTwitter" @click="handleGenTwitter">
                  🚀 生成推特专属文案
                </el-button>

                <div v-if="twitterContent" class="twitter-output">
                  <el-alert title="✅ 推特文案生成完毕！" type="success" :closable="false" show-icon style="margin-bottom: 15px;" />
                  <div class="code-block">
                    <pre>{{ twitterContent }}</pre>
                    <el-button size="small" class="copy-btn" @click="copyTwitter">Copy</el-button>
                  </div>
                  
                  <div class="publish-btns">
                    <el-button v-if="twitterMode === 'thread'" type="primary" @click="openTypefully">🚀 前往 Typefully 极速发推</el-button>
                    <el-button v-else type="primary" @click="openTwitter">↗️ 唤起推特网页版直接发布</el-button>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, RefreshRight, Back, Plus, Delete, UploadFilled } from '@element-plus/icons-vue'
import { marked } from 'marked'
import apiClient from '@/api'
import dayjs from 'dayjs'
import KnowledgeCard from './KnowledgeCard.vue'
import {
  getProjects,
  getProjectDetail,
  deleteProject,
  extractText,
  planArticle,
  generateOutline,
  refineOutline,
  DRAFT_API_URL,
  generateTwitter,
  type PlanParams,
  type Angle
} from '@/api/write'

// ==================== 状态变量 ====================
const currentStep = ref(0)
const isGenerating = ref(false)
const generationProgress = ref(0)
const runLogs = ref<string[]>([])
const logContainer = ref<HTMLElement | null>(null)

// 输入 Tab 切换
const inputTab = ref('file')

// 表单数据
const writeForm = ref<PlanParams>({
  topic: '',
  article_type: 'tech',
  word_count: 2000,
  style_tone: '犀利独到 (资深主编)',
  article_length: '标准 (1500 字)',
  must_haves: '',
  enable_web_search: false,
  source_text: '',
  auto_mode: false
})

// 项目相关
const projectId = ref<string | null>(null)
const projectList = ref<any[]>([])

// 生成结果
const generatedAngles = ref<Angle[]>([])
const selectedAngle = ref<Angle | null>(null)
const outline = ref<any[]>([])
const outlineFeedback = ref('')
const loopCount = ref(0) // 大纲版本号

// 最终文章
const finalArticle = ref('')
const draftingContent = ref('')
const critiqueNotes = ref('')

// 预览相关
const activePreviewTab = ref('text')

// Twitter 相关
const twitterMode = ref<'thread' | 'long'>('thread')
const isGeneratingTwitter = ref(false)
const twitterContent = ref('')

// ==================== 计算属性 ====================
const stepLabels = ['素材与配置', '选题定调', '大纲确认', '流式写作']

const progressPercentage = computed(() => {
  return ((currentStep.value + 1) / 4) * 100
})

const progressStatus = computed(() => {
  if (currentStep.value === 3 && !isGenerating.value) return 'success'
  return ''
})

const renderedContent = computed(() => {
  const content = finalArticle.value || draftingContent.value
  return marked(content, { breaks: true, gfm: true })
})

// ==================== 生命周期 ====================
onMounted(() => {
  fetchProjects()
})

// ==================== 方法 ====================
const handleFileChange = async (file: any) => {
  const formData = new FormData()
  formData.append('file', file.raw)
  try {
    const res: any = await extractText(formData)
    writeForm.value.source_text = res.text
    ElMessage.success('文本提取成功')
  } catch (error) {
    ElMessage.error('文件解析失败')
  }
}

const fetchProjects = async () => {
  try {
    const res: any = await getProjects()
    projectList.value = res.projects || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const startNewProject = () => {
  projectId.value = null
  currentStep.value = 0
  writeForm.value = {
    topic: '',
    article_type: 'tech',
    word_count: 2000,
    style_tone: '犀利独到 (资深主编)',
    article_length: '标准 (1500 字)',
    must_haves: '',
    enable_web_search: false,
    source_text: '',
    auto_mode: false
  }
  generatedAngles.value = []
  selectedAngle.value = null
  outline.value = []
  finalArticle.value = ''
  draftingContent.value = ''
  critiqueNotes.value = ''
  runLogs.value = []
  loopCount.value = 0
}

const loadProject = async (id: string) => {
  try {
    const res: any = await getProjectDetail(id)
    projectId.value = id
    const requirements = JSON.parse(res.requirements)
    writeForm.value = { ...requirements }
    outline.value = res.outline_data || []
    finalArticle.value = res.full_draft || ''
    critiqueNotes.value = res.research_report || ''
    
    // 根据状态判断停在哪个 Step
    if (finalArticle.value) {
      currentStep.value = 3
      generationProgress.value = 100
    } else if (outline.value.length > 0) {
      currentStep.value = 2
    } else {
      currentStep.value = 0
    }
  } catch (error) {
    ElMessage.error('加载项目失败')
  }
}

const handleDeleteProject = (id: string) => {
  ElMessageBox.confirm('确定要删除这个写作项目吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    await deleteProject(id)
    ElMessage.success('已删除')
    if (projectId.value === id) startNewProject()
    fetchProjects()
  })
}

// Step 1: 策划
const runPlanning = async () => {
  isGenerating.value = true
  try {
    const res: any = await planArticle(writeForm.value)
    projectId.value = res.project_id
    generatedAngles.value = res.angles
    currentStep.value = 1
    fetchProjects()
    
    // Auto Mode Logic
    if (writeForm.value.auto_mode && generatedAngles.value.length > 0) {
      // 自动选择第 2 个角度
      selectedAngle.value = generatedAngles.value[1] || generatedAngles.value[0]
      await runOutlineGen()
      await runDrafting()
    }
  } catch (error) {
    ElMessage.error('策划失败')
  } finally {
    isGenerating.value = false
  }
}

// Step 2: 大纲生成
const runOutlineGen = async () => {
  isGenerating.value = true
  try {
    const res: any = await generateOutline(projectId.value!, selectedAngle.value!)
    outline.value = res.outline
    currentStep.value = 2
  } catch (error) {
    ElMessage.error('大纲生成失败')
  } finally {
    isGenerating.value = false
  }
}

// 用户选择角度（非 Auto Mode）
const selectAngle = (angle: Angle) => {
  selectedAngle.value = angle
  runOutlineGen()
}

// Step 2.5: 修订大纲
const handleRefineOutline = async () => {
  if (!outlineFeedback.value) return
  isGenerating.value = true
  try {
    const res: any = await refineOutline({
      project_id: projectId.value!,
      feedback: outlineFeedback.value
    })
    outline.value = res.outline
    outlineFeedback.value = ''
    loopCount.value++
    ElMessage.success('大纲已更新')
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    isGenerating.value = false
  }
}

// Step 3: 开始写作
const startDrafting = async () => {
  await runDrafting()
}

// Step 3: Drafting (SSE)
const runDrafting = async () => {
  currentStep.value = 3
  isGenerating.value = true
  generationProgress.value = 10
  runLogs.value = ['🚀 开始流式写作流程...']
  draftingContent.value = ''
  critiqueNotes.value = ''

  try {
    const response = await fetch(DRAFT_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId.value })
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
          handleSSEResponse(data)
        }
      }
    }
  } catch (error) {
    console.error('SSE Error:', error)
    ElMessage.error('写作中断，请重试')
  } finally {
    isGenerating.value = false
    generationProgress.value = 100
  }
}

const handleSSEResponse = (data: any) => {
  if (data.logs) {
    runLogs.value.push(...data.logs)
    scrollToBottom(logContainer.value)
  }

  if (data.critique_notes) {
    critiqueNotes.value = data.critique_notes
  }
  
  if (data.node === 'Drafter') {
    // 进度模拟
    generationProgress.value = Math.min(95, generationProgress.value + 10)
  }

  if (data.node === 'FINISH') {
    finalArticle.value = data.result.final_article || data.result.full_draft
    critiqueNotes.value = data.result.critique_notes || critiqueNotes.value
    generationProgress.value = 100
    fetchProjects()
  }
}

// ==================== Twitter ====================
const handleGenTwitter = async () => {
  isGeneratingTwitter.value = true
  try {
    const res: any = await generateTwitter({
      article_content: finalArticle.value || draftingContent.value,
      mode: twitterMode.value
    })
    twitterContent.value = res.content
    ElMessage.success('推特文案已生成')
  } catch (error) {
    ElMessage.error('生成失败')
  } finally {
    isGeneratingTwitter.value = false
  }
}

const copyTwitter = () => {
  navigator.clipboard.writeText(twitterContent.value)
  ElMessage.success('已复制到剪贴板')
}

const openTypefully = () => {
  window.open('https://typefully.com/new', '_blank')
}

const openTwitter = () => {
  const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(twitterContent.value)}`
  window.open(url, '_blank')
}

// ==================== 辅助工具 ====================
const renderMarkdown = (text: string) => marked(text, { breaks: true, gfm: true })

const formatDate = (dateStr: string) => dayjs(dateStr).format('MM-DD HH:mm')

const scrollToBottom = (el: HTMLElement | null) => {
  if (el) {
    nextTick(() => {
      el.scrollTop = el.scrollHeight
    })
  }
}

const saveProject = async () => {
  // TODO: 实现保存逻辑（如果需要单独的保存接口）
  ElMessage.success('已保存到云端')
}

const rePolish = () => {
  ElMessageBox.confirm('确定要重新润色吗？', '提示', {
    type: 'warning'
  }).then(() => {
    finalArticle.value = ''
    runDrafting()
  })
}
</script>

<style scoped>
.deep-write-container {
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

.history-header h3 {
  margin: 0;
  font-size: 16px;
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
}

.del-btn {
  position: absolute;
  right: 8px;
  top: 12px;
  opacity: 0;
  transition: opacity 0.3s;
}

.history-item:hover .del-btn {
  opacity: 1;
}

/* ==================== Wizard ==================== */
.wizard-aside {
  background: #fff;
  border-right: 1px solid #dcdfe6;
}

.wizard-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.wizard-header {
  margin-bottom: 20px;
}

.wizard-header h2 {
  margin: 0 0 15px 0;
  font-size: 20px;
}

.step-label {
  margin-top: 10px;
  font-size: 14px;
  color: #606266;
}

.step-panel {
  flex: 1;
  overflow-y: auto;
}

.panel-desc {
  margin-bottom: 15px;
  color: #606266;
  font-size: 14px;
}

.action-btn {
  width: 100%;
  margin-top: 15px;
}

.switches {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

/* ==================== Angle Cards ==================== */
.angle-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.angle-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.angle-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.angle-card h4 {
  margin: 0 0 10px 0;
  font-size: 15px;
  color: #303133;
}

.angle-card .desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  margin-bottom: 8px;
}

.angle-card .reason {
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
}

.select-btn {
  padding: 4px 8px;
  font-size: 12px;
}

/* ==================== Outline ==================== */
.outline-box {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.outline-item {
  display: flex;
  gap: 12px;
  margin-bottom: 15px;
}

.outline-item .idx {
  width: 24px;
  height: 24px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
  font-weight: bold;
}

.outline-item .content {
  flex: 1;
}

.outline-item .title {
  font-weight: bold;
  font-size: 14px;
  color: #303133;
}

.outline-item .gist {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.refine-area {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.refine-area .el-input {
  flex: 4;
}

.refine-area .el-button {
  flex: 1;
}

/* ==================== Log Window ==================== */
.status-box {
  margin-top: 20px;
}

.log-window {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 8px;
  font-family: 'Courier New', Courier, monospace;
  height: 200px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.6;
}

.log-line {
  margin-bottom: 4px;
}

/* ==================== Preview Area ==================== */
.preview-main {
  background: #fff;
  padding: 0;
}

.result-area {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.article-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 40px;
  background: #fafafa;
}

.markdown-body {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px;
  background: #fff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  border-radius: 4px;
  min-height: 100%;
}

.typing-cursor {
  width: 2px;
  height: 20px;
  background: #409eff;
  display: inline-block;
  animation: blink 1s infinite;
  vertical-align: middle;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.bottom-actions {
  padding: 20px 40px;
  display: flex;
  gap: 15px;
  justify-content: center;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

/* ==================== Twitter Tool ==================== */
.twitter-tool {
  padding: 30px;
  max-width: 800px;
  margin: 0 auto;
}

.tool-desc {
  margin-bottom: 20px;
  color: #606266;
}

.mb-4 {
  margin-bottom: 15px;
}

.twitter-output {
  margin-top: 20px;
}

.code-block {
  position: relative;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 20px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  line-height: 1.6;
  max-height: 500px;
  overflow-y: auto;
}

.code-block .copy-btn {
  position: absolute;
  top: 10px;
  right: 10px;
}

.publish-btns {
  display: flex;
  gap: 15px;
  margin-top: 15px;
}

/* ==================== Tabs ==================== */
:deep(.el-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
}

:deep(.el-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tight-tabs :deep(.el-tabs__header) {
  margin-bottom: 10px;
}
</style>
