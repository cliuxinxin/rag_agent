<template>
  <div class="v3-container">
    <el-container style="height: 100%">
      
      <!-- 1. 历史记录侧边栏 -->
      <el-aside width="240px" class="history-aside">
        <div class="history-header">
          <span>📜 历史记录</span>
          <div class="header-actions">
            <el-button type="primary" link :icon="Plus" @click="resetForm" title="新建项目">新建</el-button>
            <el-button type="text" :icon="Refresh" @click="fetchHistory" title="刷新"></el-button>
          </div>
        </div>
        <el-scrollbar>
          <div v-if="historyList.length === 0" class="history-empty">暂无记录</div>
          <div 
            v-for="item in historyList" 
            :key="item.id" 
            class="history-item"
            :class="{ active: currentId === item.id }"
            @click="loadHistory(item.id)"
          >
            <div class="item-title" :title="item.title">
              {{ item.title && item.title !== '未命名项目' ? item.title : '未命名' }}
            </div>
            <div class="item-date">{{ formatDateShort(item.updated_at) }}</div>
          </div>
        </el-scrollbar>
      </el-aside>

      <!-- 2. 主内容区 -->
      <el-main class="main-workspace">
        <el-row :gutter="20" style="height: 100%">
          <!-- 左侧：配置 -->
          <el-col :span="8" class="col-input">
            <div class="panel input-panel">
              <h3>📝 创作配置</h3>
              <el-form label-position="top" size="default">
                <el-form-item label="原始素材">
                  <el-input 
                    v-model="form.content" 
                    type="textarea" 
                    :rows="10" 
                    placeholder="在此粘贴参考资料..." 
                    resize="none"
                  />
                </el-form-item>
                
                <el-form-item label="写作要求">
                  <el-input v-model="form.instruction" placeholder="例如：风格专业，逻辑清晰" />
                </el-form-item>

                <el-row :gutter="10">
                  <el-col :span="12">
                    <el-form-item label="篇幅控制">
                      <el-select v-model="form.word_count" style="width: 100%">
                        <el-option label="短讯 (500字)" value="500" />
                        <el-option label="标准 (1500字)" value="1500" />
                        <el-option label="深度 (3000字)" value="3000" />
                        <el-option label="长文 (5000字)" value="5000" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="模式">
                      <el-switch
                        v-model="form.fast_mode"
                        active-text="极速"
                        inactive-text="精修"
                      />
                    </el-form-item>
                  </el-col>
                </el-row>
                
                <el-button type="primary" class="run-btn" @click="startGeneration" :loading="isRunning">
                  {{ isRunning ? '创作中...' : '🚀 开始创作' }}
                </el-button>
              </el-form>
            </div>
            
            <div class="panel log-panel">
              <h4>⚙️ 执行日志</h4>
              <el-scrollbar ref="logScrollRef" class="log-scroll">
                <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
                <div v-for="(log, i) in logs" :key="i" class="log-item">
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-text">{{ log.text }}</span>
                </div>
              </el-scrollbar>
            </div>
          </el-col>

          <!-- 右侧：结果 -->
          <el-col :span="16" class="col-output">
            <div class="panel result-panel">
              <div class="result-header">
                <div class="header-left">
                  <h3>📄 生成结果</h3>
                  <span v-if="generatedTopic" class="topic-tag">{{ generatedTopic }}</span>
                </div>
                <div class="header-right">
                  <el-tag v-if="currentStep" effect="dark">{{ currentStep }}</el-tag>
                </div>
              </div>
              
              <div class="result-content">
                <div v-if="!displayContent && !isRunning" class="empty-state">
                  <el-icon :size="60" color="#ddd"><EditPen /></el-icon>
                  <p>在左侧输入内容并点击开始</p>
                </div>
                
                <div v-else class="content-wrapper">
                  <el-tabs v-model="activeTab" class="custom-tabs">
                    <el-tab-pane label="📝 文字排版" name="text">
                      <div class="markdown-scroll-wrapper">
                        <div class="markdown-body" v-html="renderedContent"></div>
                        <div v-if="isRunning" class="typing-indicator">
                          <span></span><span></span><span></span>
                        </div>
                      </div>
                    </el-tab-pane>
                    <el-tab-pane label="🖼️ 知识卡片" name="card">
                      <div class="card-scroll-wrapper">
                        <KnowledgeCard 
                          :title="generatedTopic || '未命名项目'" 
                          :content="displayContent" 
                          source-tag="DeepSeek Newsroom" 
                        />
                      </div>
                    </el-tab-pane>
                  </el-tabs>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import apiClient from '../api'
import { ElMessage } from 'element-plus'
import { EditPen, Refresh, Plus } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import KnowledgeCard from './KnowledgeCard.vue'
import { getProjects, getProjectDetail } from '../api/write'

const form = ref({
  content: '',
  instruction: '风格专业，逻辑清晰',
  fast_mode: false,
  word_count: '1500'
})

const isRunning = ref(false)
const logs = ref<any[]>([])
const generatedTopic = ref('')
const displayContent = ref('') 
const currentStep = ref('')
const logScrollRef = ref()
const activeTab = ref('text')
const historyList = ref<any[]>([])
const currentId = ref('')

const renderedContent = computed(() => marked(displayContent.value || ''))

// --- 核心修复：重置功能 ---
const resetForm = () => {
  currentId.value = ''
  form.value = {
    content: '',
    instruction: '风格专业，逻辑清晰',
    fast_mode: false,
    word_count: '1500'
  }
  displayContent.value = ''
  generatedTopic.value = ''
  currentStep.value = ''
  logs.value = []
  ElMessage.success('已开启新项目')
}

const fetchHistory = async () => {
  try {
    const res: any = await getProjects()
    historyList.value = (res.projects || []).filter((p: any) => p.source_type === 'newsroom_v3')
  } catch (e) { console.error(e) }
}

const loadHistory = async (id: string) => {
  try {
    const res: any = await getProjectDetail(id)
    currentId.value = id
    form.value.instruction = res.requirements || ''
    form.value.content = res.source_data || ''
    
    // 优先读取 final_article 或 full_draft
    const content = res.final_article || res.full_draft || ''
    
    if (content) {
      displayContent.value = content
      currentStep.value = '已归档'
      activeTab.value = 'text'
    } else {
      displayContent.value = ''
      ElMessage.info('暂无生成内容')
    }
    
    generatedTopic.value = res.title || '未命名项目'
    logs.value = []
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const startGeneration = async () => {
  if (!form.value.content) return ElMessage.warning('请粘贴原始素材')
  
  isRunning.value = true
  logs.value = []
  displayContent.value = ''
  generatedTopic.value = ''
  currentStep.value = '启动中...'
  activeTab.value = 'text'
  addLog('系统启动...')
  
  try {
    const response = await fetch(`${apiClient.defaults.baseURL}/api/write/v3/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = '' // 缓冲池
    
    while (true) {
      const { done, value } = await reader!.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n') // SSE 分隔符
      buffer = lines.pop() || '' // 保留未完成片段
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6)
          if (dataStr === '[DONE]') {
            isRunning.value = false
            currentStep.value = '完成'
            addLog('✅ 执行完毕')
            fetchHistory()
            continue
          }
          
          try {
            const data = JSON.parse(dataStr)
            
            if (data.error) {
              addLog('❌ 错误: ' + data.error)
              continue
            }

            if (data.logs) data.logs.forEach((l: string) => addLog(l))
            
            if (data.node) {
              const nodeMap: Record<string, string> = {
                'TopicGen': '拟定标题', 'Analyst': '分析素材', 'Architect': '设计大纲',
                'Writer': '正在撰写', 'Reviewer': '主编审阅', 'Polisher': '最终润色',
                'FastFinish': '极速归档'
              }
              currentStep.value = nodeMap[data.node] || data.node
            }
            
            if (data.generated_topic) generatedTopic.value = data.generated_topic
            if (data.display_content) displayContent.value = data.display_content
            
          } catch (e) { console.error('Parse error:', e) }
        }
      }
    }
  } catch (e) {
    ElMessage.error('请求失败')
    isRunning.value = false
  }
}

const addLog = (text: string) => {
  logs.value.push({ time: dayjs().format('HH:mm:ss'), text })
  scrollToLogBottom()
}

const scrollToLogBottom = () => {
  nextTick(() => {
    if (logScrollRef.value) {
      const wrap = logScrollRef.value.wrapRef
      if(wrap) wrap.scrollTop = wrap.scrollHeight
    }
  })
}

const formatDateShort = (str: string) => dayjs(str).format('MM-DD HH:mm')

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
/* 样式保持原样即可，重点是 template 和 script 的变化 */
.v3-container { height: 100vh; background: #f5f7fa; overflow: hidden; }
.history-aside { background: #fff; border-right: 1px solid #dcdfe6; display: flex; flex-direction: column; }
.history-header { padding: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; font-weight: bold; color: #333; }
.header-actions { display: flex; gap: 8px; }
.history-item { padding: 12px 15px; cursor: pointer; border-bottom: 1px solid #f5f7fa; transition: background 0.2s; }
.history-item:hover { background: #f5f7fa; }
.history-item.active { background: #ecf5ff; border-right: 3px solid #409eff; }
.history-empty { text-align: center; color: #999; padding: 20px; font-size: 13px; }
.item-title { font-size: 14px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #333; }
.item-date { font-size: 12px; color: #999; }
.main-workspace { padding: 20px; background: #f5f7fa; }
.panel { background: #fff; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.05); display: flex; flex-direction: column; }
.col-input { display: flex; flex-direction: column; height: 100%; gap: 15px; }
.input-panel { padding: 20px; flex-shrink: 0; }
.log-panel { flex: 1; padding: 15px 20px; overflow: hidden; background: #2b2d30; color: #ccc; }
.log-scroll { height: calc(100% - 40px); }
.log-item { font-family: monospace; font-size: 12px; margin-bottom: 4px; }
.log-time { color: #666; margin-right: 8px; }
.log-text { color: #aaa; }
.col-output { height: 100%; }
.result-panel { height: 100%; padding: 0; overflow: hidden; }
.result-header { padding: 15px 25px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
.header-left h3 { margin: 0; display: inline-block; margin-right: 15px; }
.topic-tag { font-size: 14px; font-weight: bold; color: #409eff; background: #ecf5ff; padding: 4px 10px; border-radius: 4px; }
.result-content { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.content-wrapper, .custom-tabs { height: 100%; display: flex; flex-direction: column; }
:deep(.el-tabs__content) { flex: 1; overflow: hidden; padding: 0; }
:deep(.el-tabs__header) { margin: 0; padding: 0 20px; }
.markdown-scroll-wrapper { height: 100%; overflow-y: auto; padding: 30px 40px; }
.card-scroll-wrapper { height: 100%; overflow-y: auto; padding: 20px; background: #f0f2f5; }
.empty-state { height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; color: #909399; }
.run-btn { width: 100%; font-weight: bold; }
.typing-indicator { margin-top: 20px; display: flex; gap: 5px; justify-content: center; }
.typing-indicator span { width: 6px; height: 6px; background: #409eff; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
</style>