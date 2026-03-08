<template>
  <div class="v3-container">
    <!-- 顶部步骤条 -->
    <header class="wizard-header">
      <div class="brand">📰 DeepSeek Newsroom</div>
      <el-steps :active="activeStep" simple finish-status="success" class="custom-steps">
        <el-step title="素材与配置" icon="Upload" />
        <el-step title="方向决策" icon="Compass" />
        <el-step title="生成与润色" icon="MagicStick" />
        <el-step title="成稿发布" icon="DocumentChecked" />
      </el-steps>
      <div class="history-trigger">
        <el-button @click="drawerVisible = true" circle icon="Clock" title="历史记录"></el-button>
      </div>
    </header>

    <main class="wizard-content">
      <!-- STEP 0: 配置 -->
      <transition name="fade-slide" mode="out-in">
        <div v-if="activeStep === 0" key="step0" class="step-card">
          <div class="card-title">📝 第一步：导入素材与要求</div>
          <el-form label-position="top" size="large">
            <el-form-item label="原始素材 (支持长文本)">
              <el-input 
                v-model="form.content" 
                type="textarea" 
                :rows="12" 
                placeholder="在此粘贴参考资料、会议纪要或凌乱的笔记..." 
                resize="none"
              />
            </el-form-item>
            <el-form-item label="写作意图">
              <el-input v-model="form.instruction" placeholder="例如：写一篇专业的行业分析报告，语气客观" />
            </el-form-item>
            <el-button type="primary" size="large" class="next-btn" @click="submitInit" :loading="isInitializing">
              {{ isInitializing ? '正在分析素材...' : '下一步：策划切入方向 ➡️' }}
            </el-button>
          </el-form>
        </div>

        <!-- STEP 1: 选择方向 -->
        <div v-else-if="activeStep === 1" key="step1" class="step-card">
          <div class="card-title">🧭 第二步：选择切入角度</div>
          <p class="subtitle">AI 基于素材为您策划了以下 3 个方向，请选择一个作为文章基调：</p>
          
          <div class="angles-grid">
            <div 
              v-for="angle in angleOptions" 
              :key="angle.id" 
              class="angle-box"
              :class="{ selected: selectedAngle?.id === angle.id }"
              @click="selectedAngle = angle"
            >
              <div class="angle-icon">{{ angle.id }}</div>
              <h3>{{ angle.label }}</h3>
              <p>{{ angle.description }}</p>
              <div class="check-mark" v-if="selectedAngle?.id === angle.id">
                <el-icon><Check /></el-icon>
              </div>
            </div>
          </div>

          <div class="step-actions">
            <el-button @click="activeStep = 0">上一步</el-button>
            <el-row :gutter="20" style="width: 400px; display: inline-flex; margin-left: 20px;">
               <el-col :span="12">
                 <el-select v-model="form.word_count" placeholder="字数">
                    <el-option label="1500字" value="1500" />
                    <el-option label="3000字" value="3000" />
                    <el-option label="5000字" value="5000" />
                 </el-select>
               </el-col>
               <el-col :span="12">
                 <el-switch v-model="form.fast_mode" active-text="极速模式" inactive-text="精修模式" />
               </el-col>
            </el-row>
            <el-button type="primary" @click="startRun" :disabled="!selectedAngle || isRunning" :loading="isRunning">
              开始深度写作 🚀
            </el-button>
            <el-button type="danger" @click="stopGeneration" v-if="isRunning || isInitializing">
              停止生成 🛑
            </el-button>
          </div>
        </div>

        <!-- STEP 2 & 3: 生成结果 -->
        <div v-else key="step2" class="step-card full-width">
          <div class="result-layout">
            <!-- 左侧：预览与内容 -->
            <div class="preview-panel">
              <div class="preview-header">
                <h2>{{ generatedTopic || '正在拟定标题...' }}</h2>
                <div style="display: flex; align-items: center; gap: 10px;">
                  <div class="status-badge" v-if="isRunning">
                    <span class="dot"></span> AI 正在创作中...
                  </div>
                  <el-button type="danger" size="small" @click="stopGeneration" v-if="isRunning">
                    停止
                  </el-button>
                </div>
              </div>
              <el-scrollbar height="calc(100vh - 250px)">
                <!-- 文章内容区 -->
                <div class="article-container">
                   <div class="markdown-body" v-html="renderedContent"></div>
                </div>
              </el-scrollbar>
            </div>

            <!-- 右侧：日志抽屉 -->
            <div class="log-drawer">
              <div class="drawer-header">⚙️ 思考与执行流</div>
              <el-scrollbar ref="logScroll" height="calc(100vh - 250px)">
                <div v-for="(log, i) in runLogs" :key="i" class="log-entry">
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-msg">{{ log.text }}</span>
                </div>
                <div v-if="isRunning" class="loading-spinner">
                  <el-icon class="is-loading"><Loading /></el-icon>
                </div>
              </el-scrollbar>
              
              <div class="drawer-footer" v-if="activeStep === 3">
                <el-button type="primary" @click="resetAll">开启新项目</el-button>
                <el-button @click="showDebugLogs">查看完整调试日志</el-button>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </main>

    <!-- 历史记录抽屉 -->
    <el-drawer v-model="drawerVisible" title="📜 历史项目" size="300px">
      <div v-for="p in historyList" :key="p.id" class="history-row" @click="loadProject(p.id)">
        <div class="h-title">{{ p.title || '未命名' }}</div>
        <div class="h-date">{{ formatDate(p.updated_at) }}</div>
      </div>
    </el-drawer>
    
    <!-- 详细调试日志弹窗 -->
    <el-dialog v-model="debugLogVisible" title="🔬 完整 LLM 交互日志" width="80%">
      <el-table :data="detailedLogs" stripe height="500">
        <el-table-column prop="timestamp" label="时间" width="160" />
        <el-table-column prop="stage" label="阶段" width="120" />
        <el-table-column prop="duration" label="耗时" width="100" />
        <el-table-column prop="input_prompt_preview" label="Input (Prompt)" show-overflow-tooltip />
        <el-table-column prop="output_response" label="Output (AI)" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import apiClient from '../api'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { Check, Loading, Clock } from '@element-plus/icons-vue'

// State
const activeStep = ref(0)
const isInitializing = ref(false)
const isRunning = ref(false)
const drawerVisible = ref(false)
const debugLogVisible = ref(false)
let abortController: AbortController | null = null

const form = ref({
  content: '',
  instruction: '风格专业，逻辑清晰',
  word_count: '1500',
  fast_mode: false
})

const projectId = ref('')
const angleOptions = ref<any[]>([])
const selectedAngle = ref<any>(null)
const generatedTopic = ref('')
const displayContent = ref('')
const runLogs = ref<any[]>([])
const detailedLogs = ref<any[]>([])
const historyList = ref<any[]>([])
const logScroll = ref()

const renderedContent = computed(() => marked(displayContent.value || ''))

const stopGeneration = () => {
  if (abortController) {
    abortController.abort()
    abortController = null
    isRunning.value = false
    isInitializing.value = false
    addLog('🛑 用户手动终止任务')
    ElMessage.info('已停止生成')
  }
}

// Methods
const addLog = (text: string) => {
  runLogs.value.push({ time: dayjs().format('HH:mm:ss'), text })
  nextTick(() => {
    if(logScroll.value) logScroll.value.setScrollTop(99999)
  })
}

const formatDate = (str: string) => dayjs(str).format('YYYY-MM-DD HH:mm')

// Step 1: 提交素材，获取角度
const submitInit = async () => {
  if(!form.value.content) return ElMessage.warning('请输入素材')
  isInitializing.value = true
  runLogs.value = []
  
  try {
    abortController = new AbortController()
    const response = await fetch(`${apiClient.defaults.baseURL}/api/write/v3/init_proposal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: form.value.content, instruction: form.value.instruction }),
      signal: abortController.signal
    })
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader!.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if(line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim()
          if (dataStr === '[DONE]') {
            break
          }
          const data = JSON.parse(dataStr)
          if (data.type === 'angles') {
            angleOptions.value = data.data
            projectId.value = data.pid
            activeStep.value = 1 // 进入下一步
          }
          if (data.type === 'log') {
            addLog(data.message)
          }
        }
      }
    }
  } catch(e) { 
    ElMessage.error('分析失败: ' + e) 
  } 
  finally { 
    isInitializing.value = false 
  }
}

// Step 2: 提交选择，开始生成
const startRun = async () => {
  activeStep.value = 2
  isRunning.value = true
  runLogs.value = []
  displayContent.value = ''
  generatedTopic.value = ''
  
  try {
    abortController = new AbortController()
    const response = await fetch(`${apiClient.defaults.baseURL}/api/write/v3/run_generation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId.value,
        selected_angle: selectedAngle.value,
        word_count: form.value.word_count,
        fast_mode: form.value.fast_mode
      }),
      signal: abortController.signal
    })
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader!.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim()
          if (dataStr === '[DONE]') {
            isRunning.value = false
            activeStep.value = 3 // 完成
            addLog('🎉 全文生成完毕')
            continue
          }
          const data = JSON.parse(dataStr)
          
          if (data.topic) generatedTopic.value = data.topic
          if (data.content) displayContent.value = data.content
          if (data.log) addLog(data.log)
        }
      }
    }
  } catch (e) {
    ElMessage.error('生成中断: ' + e)
    isRunning.value = false
  }
}

const resetAll = () => {
  activeStep.value = 0
  form.value.content = ''
  form.value.instruction = '风格专业，逻辑清晰'
  generatedTopic.value = ''
  displayContent.value = ''
  projectId.value = ''
  selectedAngle.value = null
  angleOptions.value = []
  runLogs.value = []
}

const showDebugLogs = async () => {
  if (!projectId.value) return
  try {
    const res: any = await (await fetch(`${apiClient.defaults.baseURL}/api/write/v3/logs/${projectId.value}`)).json()
    detailedLogs.value = res.logs
    debugLogVisible.value = true
  } catch (e) {
    ElMessage.error('获取日志失败')
  }
}

const fetchHistory = async () => {
  try {
    const res = await fetch(`${apiClient.defaults.baseURL}/api/write/v3/projects`)
    const data: any = await res.json()
    historyList.value = data.projects || []
  } catch (e) {
    console.error(e)
  }
}

const loadProject = async (id: string) => {
  try {
    const res = await fetch(`${apiClient.defaults.baseURL}/api/write/v3/project/${id}`)
    const p: any = await res.json()
    projectId.value = id
    generatedTopic.value = p.title || '未命名'
    displayContent.value = p.full_draft || ''
    activeStep.value = 3
    drawerVisible.value = false
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

onMounted(fetchHistory)
</script>

<style scoped>
.v3-container { 
  height: 100vh; 
  background: #F2F3F5; 
  display: flex; 
  flex-direction: column; 
  overflow: hidden;
}

.wizard-header { 
  background: #fff; 
  padding: 0 40px; 
  height: 60px; 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
  border-bottom: 1px solid #e0e0e0; 
  flex-shrink: 0;
}

.brand { 
  font-weight: 800; 
  font-size: 18px; 
  color: #333; 
}

.custom-steps { 
  width: 600px; 
  background: transparent !important; 
  padding: 10px 0; 
}

.wizard-content { 
  flex: 1; 
  padding: 40px; 
  display: flex; 
  justify-content: center; 
  overflow: auto;
  align-items: flex-start;
}

.step-card { 
  background: #fff; 
  border-radius: 12px; 
  padding: 40px; 
  width: 800px; 
  box-shadow: 0 4px 20px rgba(0,0,0,0.05); 
  height: fit-content;
}

.full-width { 
  width: 100%; 
  padding: 0; 
  background: transparent; 
  box-shadow: none; 
  display: flex; 
  height: 100%;
}

.card-title { 
  font-size: 24px; 
  font-weight: bold; 
  margin-bottom: 20px; 
  color: #1D1D1F; 
}

.subtitle { 
  color: #666; 
  margin-bottom: 30px; 
  font-size: 14px;
}

/* 角度选择卡片 */
.angles-grid { 
  display: grid; 
  grid-template-columns: repeat(3, 1fr); 
  gap: 20px; 
  margin-bottom: 40px; 
}

.angle-box { 
  border: 2px solid #eee; 
  border-radius: 12px; 
  padding: 25px; 
  cursor: pointer; 
  transition: all 0.2s; 
  position: relative; 
}

.angle-box:hover { 
  border-color: #409EFF; 
  transform: translateY(-5px); 
}

.angle-box.selected { 
  border-color: #409EFF; 
  background: #ECF5FF; 
}

.angle-icon { 
  font-size: 40px; 
  font-weight: 900; 
  color: #eee; 
  margin-bottom: 10px; 
}

.angle-box.selected .angle-icon { 
  color: #409EFF; 
}

.angle-box h3 {
  margin: 10px 0;
  font-size: 16px;
}

.angle-box p {
  margin: 0;
  font-size: 13px;
  color: #666;
}

.check-mark { 
  position: absolute; 
  top: 10px; 
  right: 10px; 
  color: #409EFF; 
  font-weight: bold; 
}

/* 结果布局 */
.result-layout { 
  display: flex; 
  width: 100%; 
  height: 100%; 
  gap: 20px; 
}

.preview-panel { 
  flex: 3; 
  background: #fff; 
  border-radius: 12px; 
  display: flex; 
  flex-direction: column; 
  overflow: hidden; 
}

.preview-header { 
  padding: 20px; 
  border-bottom: 1px solid #eee; 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
}

.preview-header h2 {
  margin: 0;
  font-size: 20px;
}

.log-drawer { 
  flex: 1; 
  background: #2B2D30; 
  border-radius: 12px; 
  color: #fff; 
  display: flex; 
  flex-direction: column; 
  overflow: hidden;
}

.drawer-header { 
  padding: 15px; 
  border-bottom: 1px solid #444; 
  font-weight: bold; 
  background: #232528; 
  border-radius: 12px 12px 0 0; 
  flex-shrink: 0;
}

.log-entry { 
  padding: 8px 15px; 
  font-family: monospace; 
  font-size: 12px; 
  border-bottom: 1px solid #383a3d; 
  line-height: 1.4; 
  flex-shrink: 0;
}

.log-time { 
  color: #888; 
  margin-right: 8px; 
}

.log-msg { 
  color: #ccc; 
}

.article-container { 
  padding: 40px; 
  max-width: 900px; 
  margin: 0 auto; 
}

.status-badge { 
  background: #E6F7FF; 
  color: #1890FF; 
  padding: 5px 12px; 
  border-radius: 20px; 
  font-size: 12px; 
  display: flex; 
  align-items: center; 
  gap: 6px; 
}

.dot { 
  width: 8px; 
  height: 8px; 
  background: #1890FF; 
  border-radius: 50%; 
  animation: pulse 1.5s infinite; 
}

@keyframes pulse { 
  0% { opacity: 1; } 
  50% { opacity: 0.4; } 
  100% { opacity: 1; } 
}

/* Fade Slide Transition */
.fade-slide-enter-active, .fade-slide-leave-active { 
  transition: all 0.3s ease; 
}

.fade-slide-enter-from { 
  opacity: 0; 
  transform: translateX(20px); 
}

.fade-slide-leave-to { 
  opacity: 0; 
  transform: translateX(-20px); 
}

.next-btn {
  width: 100%;
  font-weight: bold;
  margin-top: 20px;
}

.step-actions {
  margin-top: 30px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.drawer-footer {
  padding: 15px;
  border-top: 1px solid #444;
  text-align: center;
  flex-shrink: 0;
  display: flex;
  gap: 10px;
  justify-content: center;
}

.markdown-body {
  color: #333;
  line-height: 1.8;
  font-size: 16px;
}

.markdown-body h2 {
  margin-top: 30px;
  margin-bottom: 15px;
  font-size: 20px;
}

.markdown-body p {
  margin: 15px 0;
}

.loading-spinner {
  display: flex;
  justify-content: center;
  padding: 20px;
}

.is-loading {
  font-size: 24px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.history-row {
  padding: 12px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background 0.2s;
}

.history-row:hover {
  background: #f5f7fa;
}

.h-title {
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.h-date {
  font-size: 12px;
  color: #999;
}
</style>