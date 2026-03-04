<template>
  <div class="logs-container">
    <header class="logs-header">
      <h2>系统日志</h2>
      <div class="actions">
        <el-radio-group v-model="logType" size="small" @change="fetchLogs">
          <el-radio-button label="app">App Log</el-radio-button>
          <el-radio-button label="error">Error Log</el-radio-button>
        </el-radio-group>
        <el-button :icon="Download" @click="downloadLogs" circle size="small" style="margin-left: 10px;" title="下载日志" />
        <el-button :icon="Refresh" @click="fetchLogs" circle size="small" style="margin-left: 10px;" />
        <el-checkbox v-model="autoRefresh" style="margin-left: 15px;">自动刷新</el-checkbox>
      </div>
    </header>

    <main class="logs-main">
      <div ref="logContent" class="log-content">
        <div v-for="(line, idx) in logs" :key="idx" class="log-line" :class="getLogLevelClass(line)">
          {{ line }}
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Refresh, Download } from '@element-plus/icons-vue'
import apiClient from '@/api'
import { ElMessage } from 'element-plus'

const logType = ref('app')
const logs = ref<string[]>([])
const autoRefresh = ref(false)
const logContent = ref<HTMLElement | null>(null)
let timer: any = null

const fetchLogs = async () => {
  try {
    const resp: any = await apiClient.get(`/api/log/${logType.value}?n=200`)
    logs.value = resp.logs || []
    scrollToBottom()
  } catch (e) {
    console.error('获取日志失败:', e)
  }
}

const downloadLogs = () => {
  if (logs.value.length === 0) {
    ElMessage.warning('暂无日志可下载')
    return
  }
  const blob = new Blob([logs.value.join('\n')], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `system_${logType.value}_${new Date().getTime()}.log`
  a.click()
  URL.revokeObjectURL(url)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
}

const getLogLevelClass = (line: string) => {
  if (line.includes('[ERROR]')) return 'level-error'
  if (line.includes('[WARNING]')) return 'level-warning'
  if (line.includes('[DEBUG]')) return 'level-debug'
  return 'level-info'
}

watch(autoRefresh, (val) => {
  if (val) {
    timer = setInterval(fetchLogs, 3000)
  } else {
    if (timer) clearInterval(timer)
  }
})

onMounted(() => {
  fetchLogs()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.logs-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 20px;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.logs-header h2 {
  margin: 0;
  color: #fff;
}

.actions {
  display: flex;
  align-items: center;
}

.logs-main {
  flex: 1;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
}

.log-content {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  font-family: 'Fira Code', 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-line {
  margin-bottom: 2px;
}

.level-error { color: #f14c4c; }
.level-warning { color: #cca700; }
.level-debug { color: #3b8eea; }
.level-info { color: #d4d4d4; }
</style>
