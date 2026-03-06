import apiClient from './index'

export const V3_BASE = '/api/write/v3'

export function createV3Project(title: string) {
  return apiClient.post(`${V3_BASE}/create`, { title })
}

export function updateAssets(projectId: string, assets: any[]) {
  return apiClient.post(`${V3_BASE}/assets/update`, { project_id: projectId, assets })
}

export function generateV3Outline(projectId: string, requirements: string, tone: string, length: string) {
  return apiClient.post(`${V3_BASE}/outline/generate`, { project_id: projectId, requirements, tone, length })
}

export function saveV3Project(projectId: string, outlineData: any[]) {
  return apiClient.post(`${V3_BASE}/project/save`, { project_id: projectId, outline_data: outlineData })
}

export function polishText(content: string, instruction: string) {
  return apiClient.post(`${V3_BASE}/polish`, { content, instruction })
}

// 章节生成 URL，用于 fetch/EventSource
export const SECTION_STREAM_URL = `${apiClient.defaults.baseURL}${V3_BASE}/section/stream`

// 新的 DeepWrite V3 流水线接口
export const RUN_WRITE_V3_URL = `${apiClient.defaults.baseURL}${V3_BASE}/run`