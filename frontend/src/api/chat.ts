import apiClient from './index'

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface ChatStreamRequest {
  query: string
  session_id?: string
  // 这里直接使用知识库名称列表，后端会按名称加载 KB
  kb_ids?: string[]
  mode?: 'chat' | 'deep_qa' | 'deep_read'
}

export interface SSEEvent {
  type: 'progress' | 'done' | 'error'
  node?: string
  update?: any
  message?: string
  result?: any
}

/**
 * 流式聊天接口 (使用 EventSource)
 */
export async function chatStream(
  request: ChatStreamRequest,
  onMessage: (event: SSEEvent) => void,
  onError?: (error: Error) => void,
  onClose?: () => void
): Promise<void> {
  const { fetchEventSource } = await import('@microsoft/fetch-event-source')
  
  try {
    await fetchEventSource(`${apiClient.defaults.baseURL}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      onmessage: (event) => {
        try {
          const data: SSEEvent = JSON.parse(event.data)
          onMessage(data)
        } catch (e) {
          console.error('解析 SSE 事件失败:', e)
        }
      },
      onerror: (error) => {
        console.error('SSE 连接错误:', error)
        if (onError) {
          onError(error)
        }
        throw error // 抛出错误以关闭连接
      },
      onclose: () => {
        console.log('SSE 连接关闭')
        if (onClose) {
          onClose()
        }
      },
    })
  } catch (error) {
    console.error('流式聊天失败:', error)
    throw error
  }
}

/**
 * 获取会话消息历史
 */
export async function getSessionMessages(sessionId: string): Promise<Message[]> {
  const response: any = await apiClient.get(`/api/db/sessions/${sessionId}/messages`)
  return response.messages || []
}

/**
 * 创建新会话
 */
export async function createSession(title: string, mode: string = 'chat'): Promise<{ session_id: string }> {
  const response: any = await apiClient.post('/api/db/sessions', { title, mode })
  return response
}

/**
 * 获取所有会话列表
 */
export async function getSessions(): Promise<any[]> {
  const response: any = await apiClient.get('/api/db/sessions')
  return response.sessions || []
}

/**
 * 删除会话
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/api/db/sessions/${sessionId}`)
}

/**
 * 智能生成会话标题
 */
export async function generateSmartTitle(sessionId: string): Promise<{ title: string }> {
  const response: any = await apiClient.post(`/api/db/sessions/${sessionId}/generate_title`)
  return response
}
