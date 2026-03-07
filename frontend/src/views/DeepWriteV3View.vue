<template>
  <div class="v3-container">
    <el-container style="height: 100%">
      
      <!-- 1. 新增侧边栏：历史记录 -->
      <el-aside width="250px" class="history-aside">
        <div class="history-header">
          <span>📜 历史记录</span>
          <el-button type="text" icon="Refresh" @click="fetchHistory"></el-button>
        </div>
        <el-scrollbar>
          <div 
            v-for="item in historyList" 
            :key="item.id" 
            class="history-item"
            :class="{ active: currentId === item.id }"
            @click="loadHistory(item.id)"
          >
            <div class="item-title">{{ item.title || '未命名项目' }}</div>
            <div class="item-date">{{ formatDate(item.updated_at) }}</div>
          </div>
        </el-scrollbar>
      </el-aside>

      <!-- 右侧主内容区 -->
      <el-main style="padding: 0; display: flex;">
        <el-row :gutter="20" style="height: 100%; width: 100%;">
          <!-- 左侧：输入配置 -->
          <el-col :span="8" class="col-input">
            <div class="panel input-panel">
              <h3>📝 创作配置</h3>
              <el-form label-position="top">
                <!-- 删除了主题输入框 -->
                
                <el-form-item label="原始素材 (支持长文本)">
                  <el-input 
                    v-model="form.content" 
                    type="textarea" 
                    :rows="12" 
                    placeholder="在此粘贴参考资料、采访记录或乱序笔记..." 
                    resize="none"
                  />
                </el-form-item>
                
                <el-form-item label="写作要求">
                  <el-input v-model="form.instruction" placeholder="例如：风格犀利，深度分析，约2000字" />
                </el-form-item>
                
                <el-button type="primary" class="run-btn" @click="startGeneration" :loading="isRunning">
                  {{ isRunning ? '正在创作中...' : '🚀 开始深度创作' }}
                </el-button>
              </el-form>
            </div>
            
            <!-- 进度日志 (一直显示) -->
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

          <!-- 右侧：结果展示 -->
          <el-col :span="16" class="col-output">
            <div class="panel result-panel">
              <div class="result-header">
                <div class="header-left">
                  <h3>📄 生成结果</h3>
                  <!-- 自动生成的主题显示在这里 -->
                  <span v-if="generatedTopic" class="topic-tag">主题：{{ generatedTopic }}</span>
                </div>
                <div class="header-right">
                  <el-tag v-if="currentStep" effect="dark">{{ currentStep }}</el-tag>
                </div>
              </div>
              
              <div class="result-content">
                <!-- 空状态 -->
                <div v-if="!displayContent && !isRunning" class="empty-state">
                  <el-icon :size="60" color="#ddd"><EditPen /></el-icon>
                  <p>在左侧输入内容并点击开始，AI 将自动分析并生成文章</p>
                </div>
                
                <!-- 内容展示区 -->
                <div v-else class="markdown-wrapper">
                  <div class="markdown-body" v-html="renderedContent"></div>
                  <!-- 正在生成的加载条 -->
                  <div v-if="isRunning" class="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
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
import { ElMessage } from 'element-plus'
import { EditPen } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { RUN_WRITE_V3_URL } from '../api/writeV3'
import { getProjects, getProjectDetail } from '../api/write'

const form = ref({
  content: '',
  instruction: '风格专业，逻辑清晰'
})

const isRunning = ref(false)
const logs = ref<any[]>([])
const generatedTopic = ref('')
const displayContent = ref('') // 实时内容
const currentStep = ref('')
const logScrollRef = ref()

// 历史记录相关
const historyList = ref<any[]>([])
const currentId = ref('')

const renderedContent = computed(() => marked(displayContent.value))

// 获取列表
const fetchHistory = async () => {
  try {
    const res: any = await getProjects()
    // 过滤一下，只显示 V3 的项目 (source_type = 'newsroom_v3')
    historyList.value = (res.projects || []).filter((p: any) => p.source_type === 'newsroom_v3')
  } catch (e) { 
    console.error(e) 
  }
}

// 加载详情
const loadHistory = async (id: string) => {
  try {
    const res: any = await getProjectDetail(id)
    currentId.value = id
    
    // 回显内容
    form.value.instruction = res.requirements || ''
    // 注意：source_data 里存的是原始素材
    form.value.content = res.source_data || ''
    
    // 回显结果
    if (res.full_draft) {
      displayContent.value = res.full_draft
      currentStep.value = '已加载历史记录'
    }
    
    // 如果有 title
    if (res.title) generatedTopic.value = res.title
    
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const formatDate = (str: string) => {
  return dayjs(str).format('MM-DD HH:mm')
}

// 页面加载时获取
onMounted(() => {
  fetchHistory()
})

const startGeneration = async () => {
  if (!form.value.content) return ElMessage.warning('请粘贴原始素材')
  
  isRunning.value = true
  logs.value = []
  displayContent.value = ''
  generatedTopic.value = ''
  currentStep.value = '启动中...'
  addLog('系统启动，正在初始化 Agent...')
  
  try {
    const response = await fetch(`${RUN_WRITE_V3_URL}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    
    while (true) {
      const { done, value } = await reader!.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6)
          if (dataStr === '[DONE]') {
            isRunning.value = false
            currentStep.value = '完成'
            addLog('✅ 全部流程执行完毕！')
            // 刷新历史记录列表
            fetchHistory()
            continue
          }
          
          try {
            const data = JSON.parse(dataStr)
            
            if (data.error) {
              ElMessage.error('Error: ' + data.error)
              addLog('❌ 发生错误: ' + data.error)
              continue
            }

            // 1. 更新日志
            if (data.logs && data.logs.length) {
              data.logs.forEach((l: string) => addLog(l))
            }
            
            // 2. 更新状态
            if (data.node) {
              const nodeMap: Record<string, string> = {
                'TopicGen': '拟定标题',
                'Analyst': '分析素材',
                'Architect': '设计大纲',
                'Writer': '正在撰写',
                'Reviewer': '主编审阅',
                'Polisher': '最终润色'
              }
              currentStep.value = nodeMap[data.node] || data.node
            }
            
            // 3. 更新主题
            if (data.generated_topic) {
              generatedTopic.value = data.generated_topic
            }
            
            // 4. 更新正文 (核心修复：实时显示草稿)
            if (data.display_content) {
              displayContent.value = data.display_content
            }
            
          } catch (e) { console.error(e) }
        }
      }
    }
  } catch (e) {
    ElMessage.error('请求失败')
    isRunning.value = false
  }
}

const addLog = (text: string) => {
  logs.value.push({
    time: dayjs().format('HH:mm:ss'),
    text
  })
  
  // 强制滚动到底部
  nextTick(() => {
    if (logScrollRef.value) {
      // Element Plus Scrollbar 的 API
      const wrap = logScrollRef.value.wrapRef
      if(wrap) wrap.scrollTop = wrap.scrollHeight
    }
  })
}
</script>

<style scoped>
.v3-container {
  height: 100vh;
  background: #f5f7fa;
  overflow: hidden;
}

.el-container {
  height: 100%;
}

.el-main {
  padding: 20px !important;
  height: 100%;
  overflow: hidden;
}

/* 侧边栏样式 */
.history-aside {
  background: #fff;
  border-right: 1px solid #eee;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.history-header {
  padding: 15px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
  color: #333;
}

.history-item {
  padding: 12px 15px;
  cursor: pointer;
  border-bottom: 1px solid #f5f7fa;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f5f7fa;
}

.history-item.active {
  background: #ecf5ff;
  border-right: 3px solid #409eff;
}

.item-title {
  font-size: 14px;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-date {
  font-size: 12px;
  color: #999;
}

.panel {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.04);
  display: flex;
  flex-direction: column;
}

/* 左侧布局 */
.col-input {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 20px;
}

.input-panel {
  padding: 20px;
  flex-shrink: 0; /* 防止被压缩 */
}

.log-panel {
  flex: 1; /* 占据剩余空间 */
  padding: 15px 20px;
  overflow: hidden;
  background: #2b2d30; /* 深色日志背景 */
  color: #ccc;
}

.log-panel h4 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 14px;
  color: #fff;
  border-bottom: 1px solid #444;
  padding-bottom: 8px;
}

.log-scroll {
  height: calc(100% - 40px);
}

.log-item {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  margin-bottom: 6px;
  line-height: 1.4;
}

.log-time {
  color: #666;
  margin-right: 8px;
}

.log-text {
  color: #a9b7c6;
}

.log-empty {
  color: #555;
  text-align: center;
  margin-top: 20px;
  font-size: 12px;
}

.run-btn {
  width: 100%;
  margin-top: 10px;
  height: 40px;
  font-weight: bold;
}

/* 右侧布局 */
.col-output {
  height: 100%;
}

.result-panel {
  height: 100%;
  padding: 0; /* Header 单独处理 padding */
  overflow: hidden;
}

.result-header {
  padding: 15px 25px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
}

.header-left h3 {
  margin: 0;
  display: inline-block;
  margin-right: 15px;
}

.topic-tag {
  font-size: 14px;
  font-weight: bold;
  color: #409eff;
  background: #ecf5ff;
  padding: 4px 10px;
  border-radius: 4px;
}

.result-content {
  flex: 1;
  overflow-y: auto;
  padding: 30px 40px;
  background: #fff;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
}

.empty-state p {
  margin-top: 20px;
}

.markdown-body {
  line-height: 1.8;
  color: #333;
}

/* 打字机光标动画 */
.typing-indicator {
  margin-top: 20px;
  display: flex;
  gap: 5px;
  justify-content: center;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #409eff;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>