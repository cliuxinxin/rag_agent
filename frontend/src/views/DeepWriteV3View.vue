<template>
  <div class="v3-container">
    <el-row :gutter="20" style="height: 100%">
      <!-- 左侧：输入配置 -->
      <el-col :span="8" class="col-input">
        <div class="panel">
          <h3>📝 创作配置</h3>
          <el-form label-position="top">
            <el-form-item label="文章主题">
              <el-input v-model="form.topic" placeholder="例如：2024 AI 行业发展趋势" />
            </el-form-item>
            <el-form-item label="原始素材 (支持长文本)">
              <el-input 
                v-model="form.content" 
                type="textarea" 
                :rows="15" 
                placeholder="在此粘贴参考资料、采访记录或乱序笔记..." 
              />
            </el-form-item>
            <el-form-item label="写作要求">
              <el-input v-model="form.instruction" placeholder="例如：风格犀利，深度分析，约2000字" />
            </el-form-item>
            <el-button type="primary" class="run-btn" @click="startGeneration" :loading="isRunning">
              🚀 开始深度创作
            </el-button>
          </el-form>
        </div>
        
        <!-- 进度日志 -->
        <div class="panel log-panel" v-if="logs.length">
          <h4>⚙️ 执行日志</h4>
          <el-scrollbar height="200px" ref="logScroll">
            <div v-for="(log, i) in logs" :key="i" class="log-item">{{ log }}</div>
          </el-scrollbar>
        </div>
      </el-col>

      <!-- 右侧：结果展示 -->
      <el-col :span="16" class="col-output">
        <div class="panel result-panel">
          <div class="result-header">
            <h3>📄 生成结果</h3>
            <el-tag v-if="currentStep">{{ currentStep }}</el-tag>
          </div>
          
          <div v-if="!finalArticle" class="empty-state">
            <el-empty description="AI 正在思考中，请稍候..." v-if="isRunning" />
            <el-empty description="在左侧输入内容并点击开始" v-else />
          </div>
          
          <div v-else class="markdown-body" v-html="renderedContent"></div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import { RUN_WRITE_V3_URL } from '../api/writeV3'
import apiClient from '../api/index'

const form = ref({
  topic: '',
  content: '',
  instruction: '风格专业，逻辑清晰'
})

const isRunning = ref(false)
const logs = ref<string[]>([])
const finalArticle = ref('')
const currentStep = ref('')
const logScroll = ref()

const renderedContent = computed(() => marked(finalArticle.value))

const startGeneration = async () => {
  if (!form.value.content || !form.value.topic) return ElMessage.warning('请填写完整')
  
  isRunning.value = true
  logs.value = ['🚀 系统启动，正在初始化 Agent...']
  finalArticle.value = ''
  currentStep.value = '准备中'
  
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
      
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6)
          if (dataStr === '[DONE]') {
            isRunning.value = false
            logs.value.push('✅ 全部完成！')
            continue
          }
          
          try {
            const data = JSON.parse(dataStr)
            
            // 更新日志
            if (data.logs && data.logs.length) {
              logs.value.push(...data.logs)
              scrollToLogBottom()
            }
            
            // 更新状态标签
            if (data.node) currentStep.value = `正在执行: ${data.node}`
            
            // 如果是最终结果
            if (data.final_article) {
              finalArticle.value = data.final_article
            }
            
          } catch (e) { console.error(e) }
        }
      }
    }
  } catch (e) {
    ElMessage.error('生成出错')
    isRunning.value = false
  }
}

const scrollToLogBottom = () => {
  nextTick(() => {
    if (logScroll.value) {
      const wrap = logScroll.value.wrapRef
      wrap.scrollTop = wrap.scrollHeight
    }
  })
}
</script>

<style scoped>
.v3-container {
  height: 100vh;
  background: #f5f7fa;
  padding: 20px;
}
.panel {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}
.col-input {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.col-output {
  height: 100%;
}
.result-panel {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.run-btn {
  width: 100%;
  margin-top: 10px;
}
.log-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.log-item {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  font-family: monospace;
}
.markdown-body {
  padding: 20px;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
  margin-bottom: 20px;
}
</style>