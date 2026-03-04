import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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
    path: '/deep-write',
    name: 'DeepWrite',
    component: () => import('@/views/DeepWriteView.vue'),
    meta: { title: '深度写作' }
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
  next()
})

export default router
