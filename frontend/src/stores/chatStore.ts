import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Message, SSEEvent } from '@/api/chat'
import * as chatApi from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  // State
  const currentSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const sessions = ref<any[]>([])
  const isLoading = ref(false)
  const progressNodes = ref<SSEEvent[]>([])
  const error = ref<string | null>(null)

  // Getters
  const hasMessages = computed(() => messages.value.length > 0)
  const isChatting = computed(() => isLoading.value)

  // Actions
  /**
   * 加载会话列表
   */
  async function loadSessions() {
    try {
      sessions.value = await chatApi.getSessions()
    } catch (err: any) {
      console.error('加载会话列表失败:', err)
      error.value = err.message
    }
  }

  /**
   * 创建新会话
   */
  async function createNewSession(title: string, mode: string = 'chat') {
    try {
      const result = await chatApi.createSession(title, mode)
      currentSessionId.value = result.session_id
      messages.value = []
      await loadSessions() // 刷新列表
      return result.session_id
    } catch (err: any) {
      console.error('创建会话失败:', err)
      error.value = err.message
      throw err
    }
  }

  /**
   * 加载指定会话的消息
   */
  async function loadSessionMessages(sessionId: string) {
    try {
      currentSessionId.value = sessionId
      messages.value = await chatApi.getSessionMessages(sessionId)
      error.value = null
    } catch (err: any) {
      console.error('加载消息失败:', err)
      error.value = err.message
    }
  }

  /**
   * 删除会话
   */
  async function removeSession(sessionId: string) {
    try {
      await chatApi.deleteSession(sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        messages.value = []
      }
      await loadSessions() // 刷新列表
    } catch (err: any) {
      console.error('删除会话失败:', err)
      error.value = err.message
      throw err
    }
  }

  /**
   * 发送消息 (流式)
   */
  async function sendMessage(query: string, onProgress?: (event: SSEEvent) => void) {
    if (!query.trim()) return
    
    isLoading.value = true
    progressNodes.value = []
    error.value = null

    // 添加用户消息到本地显示
    messages.value.push({
      role: 'user',
      content: query,
    })

    try {
      // 如果没有当前会话，创建一个
      if (!currentSessionId.value) {
        await createNewSession('新对话', 'chat')
      }

      // 调用流式接口
      await chatApi.chatStream(
        {
          query,
          session_id: currentSessionId.value || undefined,
          mode: 'chat',
        },
        (event: SSEEvent) => {
          if (event.type === 'progress') {
            progressNodes.value.push(event)
            if (onProgress) {
              onProgress(event)
            }
          } else if (event.type === 'done') {
            // 完成后重新加载消息历史
            if (currentSessionId.value) {
              loadSessionMessages(currentSessionId.value)
            }
            isLoading.value = false
          }
        },
        (err: Error) => {
          console.error('流式聊天错误:', err)
          error.value = err.message
          isLoading.value = false
        },
        () => {
          console.log('连接关闭')
        }
      )
    } catch (err: any) {
      console.error('发送消息失败:', err)
      error.value = err.message
      isLoading.value = false
    }
  }

  /**
   * 清空当前对话
   */
  function clearCurrentChat() {
    messages.value = []
    progressNodes.value = []
    error.value = null
  }

  return {
    // State
    currentSessionId,
    messages,
    sessions,
    isLoading,
    progressNodes,
    error,
    // Getters
    hasMessages,
    isChatting,
    // Actions
    loadSessions,
    createNewSession,
    loadSessionMessages,
    removeSession,
    sendMessage,
    clearCurrentChat,
  }
})
