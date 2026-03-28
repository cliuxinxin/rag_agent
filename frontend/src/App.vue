<template>
  <div class="app-layout">
    <!-- 左侧全局侧边栏 -->
    <aside v-if="route.name !== 'Login'" class="sidebar" :class="{ collapsed: isCollapse }">
      <div class="logo-area">
        <h2 v-if="!isCollapse">DeepSeek RAG</h2>
        <el-button 
          class="collapse-btn" 
          type="text" 
          @click="isCollapse = !isCollapse"
        >
          <el-icon><Expand v-if="isCollapse" /><Fold v-else /></el-icon>
        </el-button>
      </div>

      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical"
        background-color="#f8f9fa"
        text-color="#303133"
        active-text-color="#409EFF"
        router
        :collapse="isCollapse"
      >
        <el-menu-item index="/">
          <el-icon><ChatDotRound /></el-icon>
          <span>对话</span>
        </el-menu-item>

        <el-menu-item index="/deep-mastery">
          <el-icon><Reading /></el-icon>
          <span>深度掌握</span>
        </el-menu-item>

        <el-menu-item index="/skill-agent">
          <el-icon><MagicStick /></el-icon>
          <span>技能智能体</span>
        </el-menu-item>

        <el-menu-item index="/deep-qa">
          <el-icon><QuestionFilled /></el-icon>
          <span>深度追问</span>
        </el-menu-item>

        <el-menu-item index="/deep-read">
          <el-icon><Document /></el-icon>
          <span>深度阅读</span>
        </el-menu-item>

        <el-menu-item index="/reading-copilot">
          <el-icon><List /></el-icon>
          <span>长文伴读</span>
        </el-menu-item>

        <el-menu-item index="/deep-write-v3">
          <el-icon><Edit /></el-icon>
          <span>新闻工作室</span>
        </el-menu-item>

        <el-menu-item index="/kb-management">
          <el-icon><Files /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>

        <el-menu-item index="/ppt-generator">
          <el-icon><Monitor /></el-icon>
          <span>PPT 生成</span>
        </el-menu-item>

        <el-menu-item index="/system-logs">
          <el-icon><Setting /></el-icon>
          <span>系统日志</span>
        </el-menu-item>

        <el-menu-item @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <!-- 右侧主内容区 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, Document, Files, Monitor, Setting, Reading, MagicStick, SwitchButton, QuestionFilled, Fold, Expand, Edit, List } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => route.path || '/')
const isCollapse = ref(window.innerWidth < 1024)

// 响应式监听
window.addEventListener('resize', () => {
  if (window.innerWidth < 1024) {
    isCollapse.value = true
  }
})

const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    ElMessage.success('已退出登录')
    router.push('/login')
  }).catch(() => {})
}
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  width: 100%;
  height: 100vh;
}

.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  background-color: #f8f9fa;
  border-right: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
}

.sidebar.collapsed {
  width: 64px;
}

.logo-area {
  padding: 10px 20px;
  height: 60px;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-area h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
}

.collapse-btn {
  padding: 8px !important;
  font-size: 20px;
  color: #606266;
}

.el-menu-vertical:not(.el-menu--collapse) {
  width: 240px;
}

.main-content {
  flex: 1;
  background-color: #fff;
  overflow: hidden;
  position: relative;
}
</style>
