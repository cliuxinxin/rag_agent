import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { title: '智能对话' }
  },
  {
    path: '/deep-read',
    name: 'DeepRead',
    component: () => import('@/views/DeepReadView.vue'),
    meta: { title: '深度阅读' }
  },
  {
    path: '/kb-management',
    name: 'KBManagement',
    component: () => import('@/views/KBManagement.vue'),
    meta: { title: '知识库管理' }
  },
  {
    path: '/ppt-generator',
    name: 'PPTGenerator',
    component: () => import('@/views/PPTGenerator.vue'),
    meta: { title: 'PPT 生成' }
  },
  {
    path: '/system-logs',
    name: 'SystemLogs',
    component: () => import('@/views/SystemLogsView.vue'),
    meta: { title: '系统日志' }
  },
  {
    path: '/deep-mastery',
    name: 'DeepMastery',
    component: () => import('@/views/DeepMasteryView.vue'),
    meta: { title: '深度掌握' }
  },
  {
    path: '/skill-agent',
    name: 'SkillAgent',
    component: () => import('@/views/SkillAgentView.vue'),
    meta: { title: '技能智能体' }
  },
  {
    path: '/deep-qa',
    name: 'DeepQA',
    component: () => import('@/views/DeepQAView.vue'),
    meta: { title: '深度追问' }
  },
  {
    path: '/deep-write-v3',
    name: 'DeepWriteV3',
    component: () => import('@/views/DeepWriteV3View.vue'),
    meta: { title: '新闻工作室' }
  },
  {
    path: '/reading-copilot',
    name: 'ReadingCopilot',
    component: () => import('@/views/ReadingCopilotView.vue'),
    meta: { title: '长文伴读' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  if (to.meta?.title) {
    document.title = `${to.meta.title} - DeepSeek RAG Agent`
  }

  // 登录检查
  const token = localStorage.getItem('token')
  if (!to.meta?.public && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})

export default router
