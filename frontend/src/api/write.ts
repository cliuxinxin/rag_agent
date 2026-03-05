/**
 * 深度写作模块 API 封装
 * 提供新闻工作室（DeepWrite）相关的所有接口调用
 */
import apiClient from './index'

// ==================== 类型定义 ====================

export interface PlanParams {
  topic: string
  article_type: string
  word_count: number
  source_text?: string
  style_tone: string
  article_length: string
  must_haves: string
  enable_web_search: boolean
  auto_mode: boolean
}

export interface Angle {
  title: string
  desc: string
  reasoning: string
}

export interface OutlineItem {
  title: string
  gist: string
  key_facts?: string
}

export interface RefineOutlineParams {
  project_id: string
  feedback: string
}

export interface TwitterParams {
  article_content: string
  mode: 'thread' | 'long'
}

export interface WritingProject {
  id: string
  title: string
  requirements: string
  outline_data: any[]
  full_draft: string
  research_report: string
  created_at: string
  updated_at: string
}

// ==================== API 方法 ====================

/**
 * 获取所有写作项目列表
 */
export function getProjects() {
  return apiClient.get('/api/write/projects')
}

/**
 * 获取单个项目详情
 */
export function getProjectDetail(id: string) {
  return apiClient.get(`/api/write/projects/${id}`)
}

/**
 * 删除写作项目
 */
export function deleteProject(id: string) {
  return apiClient.delete(`/api/write/projects/${id}`)
}

/**
 * 从上传的文件中提取文本内容
 */
export function extractText(formData: FormData) {
  return apiClient.post('/api/write/extract_text', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * [Step 1] 策划阶段 - 生成文章角度
 */
export function planArticle(data: PlanParams) {
  return apiClient.post('/api/write/plan', data)
}

/**
 * [Step 2] 生成大纲 - 根据选定的角度生成文章大纲
 */
export function generateOutline(projectId: string, selectedAngle: Angle) {
  return apiClient.post('/api/write/outline', {
    project_id: projectId,
    selected_angle: selectedAngle
  })
}

/**
 * [Step 2.5] 修订大纲 - 根据用户反馈修改大纲
 */
export function refineOutline(projectId: string, feedback: string) {
  return apiClient.post('/api/write/refine_outline', {
    project_id: projectId,
    feedback: feedback
  })
}

/**
 * [Step 3] 写作接口 URL（用于 SSE 流式调用）
 * 注意：此接口直接使用 fetch 调用，不走 axios 拦截器
 */
export const DRAFT_API_URL = `${apiClient.defaults.baseURL}/api/write/draft`
