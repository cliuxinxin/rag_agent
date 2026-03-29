<template>
  <div class="reading-copilot" :class="themeClass">
    <div class="top-bar">
      <div class="top-bar-left">
        <el-button @click="showImportDialog = true" type="primary" :icon="Plus">导入长文本</el-button>
        <el-button @click="showSessions = !showSessions" :icon="List">历史项目</el-button>
      </div>

      <div class="top-bar-right" v-if="currentSessionId">
        <el-button-group>
          <el-button @click="viewMode = 'formatted'" :type="viewMode === 'formatted' ? 'primary' : ''">伴读稿</el-button>
          <el-button @click="viewMode = 'raw'" :type="viewMode === 'raw' ? 'primary' : ''">原文</el-button>
        </el-button-group>

        <el-button-group>
          <el-button @click="adjustFontSize(-1)" :icon="Minus">字号</el-button>
          <el-button @click="adjustFontSize(1)" :icon="Plus">字号</el-button>
        </el-button-group>

        <el-button-group class="theme-switcher">
          <el-button @click="currentTheme = 'light'" :type="currentTheme === 'light' ? 'primary' : ''">日间</el-button>
          <el-button @click="currentTheme = 'paper'" :type="currentTheme === 'paper' ? 'primary' : ''">纸感</el-button>
          <el-button @click="currentTheme = 'dark'" :type="currentTheme === 'dark' ? 'primary' : ''">夜间</el-button>
        </el-button-group>

        <el-button-group class="lens-switcher">
          <el-button @click="activeLens = 'all'" :type="activeLens === 'all' ? 'primary' : ''">全部</el-button>
          <el-button @click="activeLens = 'data'" :type="activeLens === 'data' ? 'primary' : ''">数据</el-button>
          <el-button @click="activeLens = 'entity'" :type="activeLens === 'entity' ? 'primary' : ''">概念</el-button>
          <el-button @click="activeLens = 'logic'" :type="activeLens === 'logic' ? 'primary' : ''">逻辑</el-button>
        </el-button-group>

        <el-button plain @click="runArticleQuiz">考考我</el-button>
        <el-button plain @click="openInDeepRead">送去深读</el-button>
        <el-button plain @click="openInDeepQA()">去深挖</el-button>
      </div>
    </div>

    <div class="main-content" v-if="currentSessionId">
      <aside class="sidebar-left">
        <el-tabs v-model="leftSidebarTab" type="border-card">
          <el-tab-pane label="目录" name="toc">
            <div class="toc-list">
              <button
                v-for="heading in tableOfContents"
                :key="heading.id"
                class="toc-item"
                :class="{ active: heading.id === currentSectionId }"
                @click="scrollToHeading(heading.id)"
              >
                <span class="toc-title">{{ heading.text }}</span>
                <span class="toc-meta">{{ heading.word_count || 0 }}字</span>
              </button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="章节" name="sections">
            <div class="section-cards">
              <article
                v-for="section in sectionSummaries"
                :key="section.id"
                class="section-card"
                :class="{ active: section.id === currentSectionId }"
              >
                <div class="section-card-header">
                  <h4>{{ section.title }}</h4>
                  <span>{{ section.word_count || 0 }}字</span>
                </div>
                <p>{{ section.summary }}</p>
                <ul v-if="section.takeaways?.length">
                  <li v-for="point in section.takeaways" :key="point">{{ point }}</li>
                </ul>
                <div v-if="section.question" class="section-question">可追问：{{ section.question }}</div>
                <div class="section-actions">
                  <el-button size="small" @click="scrollToHeading(section.id)">跳到这里</el-button>
                  <el-button size="small" type="primary" plain @click="useSuggestedQuestion(section.question || `这节《${section.title}》最重要的意思是什么？`)">追问这节</el-button>
                </div>
              </article>
            </div>
          </el-tab-pane>
        </el-tabs>
      </aside>

      <main
        class="reading-area"
        ref="readingAreaRef"
        @mouseup="handleTextSelection"
        @click="hideSelectionMenu"
        @scroll="handleReadingScroll"
        :style="{ fontSize: `${fontSize}px`, lineHeight: String(lineHeight) }"
        :class="readingAreaClasses"
      >
        <div class="reading-progress-shell">
          <div class="reading-progress-bar" :style="{ width: `${readingProgress}%` }"></div>
        </div>

        <div class="reading-status">
          <span>阅读进度 {{ Math.round(readingProgress) }}%</span>
          <span>{{ currentSectionTitle || '准备开始' }}</span>
        </div>

        <div v-if="viewMode === 'formatted'" v-html="renderedMarkdown" class="markdown-content"></div>
        <div v-else class="raw-content">{{ sessionData?.raw_text_content || '' }}</div>
      </main>

      <aside class="sidebar-right">
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane label="导读" name="guide">
            <div class="guide-card">
              <div class="hero-summary">
                <div class="hero-label">一句话总结</div>
                <p>{{ sessionData?.summary_data?.summary || '加载中...' }}</p>
              </div>

              <div class="guide-actions">
                <el-button size="small" @click="runArticleQuiz">考考我</el-button>
                <el-button size="small" @click="useSuggestedQuestion('这篇文章最值得质疑的地方是什么？')">找漏洞</el-button>
                <el-button size="small" @click="useSuggestedQuestion('作者有哪些隐含前提没有说透？')">找前提</el-button>
              </div>

              <section class="guide-section">
                <h4>核心看点</h4>
                <ul>
                  <li v-for="point in sessionData?.summary_data?.takeaways || []" :key="point">{{ point }}</li>
                </ul>
              </section>

              <section class="guide-section" v-if="guideClaims.length">
                <h4>关键判断</h4>
                <div class="claim-list">
                  <article v-for="(claim, index) in guideClaims" :key="`${claim.claim}-${index}`" class="claim-card">
                    <p class="claim-text">{{ claim.claim }}</p>
                    <p class="claim-evidence">{{ claim.evidence }}</p>
                    <div class="claim-actions">
                      <el-button size="small" @click="jumpToClaim(claim.section_id)">跳转原文</el-button>
                      <el-button size="small" type="primary" plain @click="useSuggestedQuestion(`文中“${claim.claim}”的依据够不够强？`)">继续追问</el-button>
                    </div>
                  </article>
                </div>
              </section>

              <section class="guide-section" v-if="guideTensions.length">
                <h4>值得怀疑的地方</h4>
                <ul>
                  <li v-for="item in guideTensions" :key="item">{{ item }}</li>
                </ul>
              </section>

              <section class="guide-section" v-if="openQuestions.length">
                <h4>继续深挖</h4>
                <div class="question-chips">
                  <button
                    v-for="question in openQuestions"
                    :key="question"
                    class="question-chip"
                    @click="useSuggestedQuestion(question)"
                  >
                    {{ question }}
                  </button>
                </div>
              </section>

              <div class="meta-info">
                <span>字数 {{ sessionData?.word_count || 0 }}</span>
                <span>预计 {{ sessionData?.read_time || 0 }} 分钟</span>
                <span>切块 {{ sessionData?.chunk_count || 0 }}</span>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="播客" name="podcast">
            <div class="podcast-card">
              <div
                v-for="(item, index) in sessionData?.summary_data?.podcast_script || []"
                :key="`${item.speaker}-${index}`"
                class="podcast-turn"
                :class="item.speaker === 'A' ? 'host' : 'guest'"
              >
                <div class="speaker">{{ item.speaker === 'A' ? '主播A' : '嘉宾B' }}</div>
                <p>{{ item.text }}</p>
              </div>
              <el-empty v-if="!(sessionData?.summary_data?.podcast_script || []).length" description="还没有播客脚本" />
            </div>
          </el-tab-pane>

          <el-tab-pane label="图谱" name="graph">
            <div class="graph-card">
              <div ref="graphRef" class="knowledge-graph"></div>
              <p class="graph-hint">点节点会自动生成一个追问，方便继续伴读。</p>
            </div>
          </el-tab-pane>

          <el-tab-pane label="伴读问答" name="chat">
            <div class="chat-container">
              <div class="chat-messages" ref="chatMessagesRef">
                <div
                  v-for="(msg, index) in chatMessages"
                  :key="index"
                  class="message-item"
                  :class="msg.role"
                >
                  <div
                    v-if="msg.quote_text"
                    class="quote-text"
                    :class="{ clickable: !!msg.quote_anchor?.section_id }"
                    @click="scrollToAnchor(msg.quote_anchor)"
                  >
                    <div class="quote-head">
                      <span class="quote-label">{{ msg.quote_anchor?.section_title || '引用原文' }}</span>
                      <span v-if="msg.quote_anchor?.section_id" class="quote-jump">跳回原文</span>
                    </div>
                    <p>{{ msg.quote_text }}</p>
                  </div>

                  <div v-if="msg.role === 'assistant'" class="message-content assistant-markdown markdown-body" v-html="renderMessageMarkdown(msg.content)"></div>
                  <div v-else class="message-content user-text">{{ msg.content || '围绕引用继续发问' }}</div>
                </div>

                <div v-if="isStreaming" class="message-item assistant">
                  <div
                    v-if="streamingMeta.quote_anchor?.section_title || streamingMeta.references.length"
                    class="quote-text"
                    :class="{ clickable: !!streamingMeta.quote_anchor?.section_id }"
                    @click="scrollToAnchor(streamingMeta.quote_anchor)"
                  >
                    <div class="quote-head">
                      <span class="quote-label">{{ streamingMeta.quote_anchor?.section_title || '参考段落' }}</span>
                      <span v-if="streamingMeta.quote_anchor?.section_id" class="quote-jump">跳回原文</span>
                    </div>
                    <p>{{ streamingMeta.references[0]?.preview || '助手正在结合相关段落作答…' }}</p>
                  </div>
                  <div class="message-content assistant-markdown markdown-body" v-html="renderMessageMarkdown(streamingContent) + '<span class=&quot;cursor&quot;>▋</span>'"></div>
                </div>
              </div>

              <div class="chat-input-area">
                <div v-if="pendingQuoteText" class="pending-quote">
                  <span>{{ pendingQuoteAnchor?.section_title || '引用片段' }}：{{ pendingQuoteText }}</span>
                  <el-button @click="clearPendingQuote" type="text" :icon="Close" size="small"></el-button>
                </div>

                <div class="quick-question-row" v-if="quickQuestions.length">
                  <button
                    v-for="question in quickQuestions"
                    :key="question"
                    class="quick-question"
                    @click="useSuggestedQuestion(question)"
                  >
                    {{ question }}
                  </button>
                </div>

                <el-input
                  v-model="userInput"
                  type="textarea"
                  :rows="3"
                  placeholder="输入你的问题，或者先划词再发问…"
                  @keyup.enter="sendMessage"
                ></el-input>
                <div class="chat-actions">
                  <el-button @click="sendMessage" type="primary" :disabled="isStreaming || (!userInput.trim() && !pendingQuoteText)">发送</el-button>
                  <el-button plain @click="useSuggestedQuestion('请帮我把这篇文章讲给完全不了解的人听')">转述给朋友</el-button>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </aside>
    </div>

    <div class="empty-state" v-else>
      <el-empty description="导入长文本开始 AI 伴读体验">
        <el-button @click="showImportDialog = true" type="primary" :icon="Plus">导入文本</el-button>
      </el-empty>
    </div>

    <div
      class="selection-menu"
      v-if="showSelectionMenu"
      :style="{ left: `${menuPosition.x}px`, top: `${menuPosition.y}px` }"
    >
      <el-button @click="executeAction('explain')" size="small">解释</el-button>
      <el-button @click="executeAction('translate')" size="small">翻译</el-button>
      <el-button @click="executeAction('summarize')" size="small">总结</el-button>
      <el-button @click="executeAction('explain_5yr')" size="small">5岁秒懂</el-button>
      <el-button @click="executeAction('extract_quote')" size="small">提炼金句</el-button>
      <el-button @click="executeAction('feynman_quiz')" size="small">反问我</el-button>
      <el-button @click="quoteSelection" size="small">发问</el-button>
    </div>

    <el-dialog v-model="showImportDialog" title="导入长文本" width="640px">
      <el-tabs v-model="importMode">
        <el-tab-pane label="粘贴文本" name="text">
          <el-input
            v-model="importText"
            type="textarea"
            :rows="16"
            placeholder="粘贴你要阅读的长文本..."
          />
        </el-tab-pane>

        <el-tab-pane label="上传 PDF" name="pdf">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".pdf,application/pdf"
            :on-change="handleImportFileChange"
            :on-remove="handleImportFileRemove"
            class="import-upload"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽 PDF 到此处或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持论文、报告、白皮书等 PDF 文档，系统会先提取文本再进入伴读。</div>
            </template>
          </el-upload>

          <div v-if="selectedImportFile" class="selected-file-card">
            <div class="selected-file-name">{{ selectedImportFile.name }}</div>
            <div class="selected-file-meta">{{ formatFileSize(selectedImportFile.size) }}</div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="closeImportDialog">取消</el-button>
        <el-button @click="initCopilot" type="primary" :loading="isImporting">开始处理</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="showSessions" title="历史阅读项目" size="420px">
      <div class="session-list">
        <button
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="loadSession(session.id)"
        >
          <div class="session-title">{{ session.title }}</div>
          <div class="session-meta">
            <span>{{ session.word_count }}字 · {{ session.read_time }}分钟</span>
            <span>{{ formatTime(session.created_at) }}</span>
          </div>
        </button>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { Close, List, Minus, Plus, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import apiClient from '@/api'

interface QuoteAnchor {
  chunk_id?: string
  section_id?: string
  section_title?: string
  preview?: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  quote_text?: string
  quote_anchor?: QuoteAnchor | null
  references?: QuoteAnchor[]
}

interface SessionData {
  title: string
  word_count: number
  read_time: number
  markdown_content: string
  raw_text_content: string
  summary_data: any
  messages: ChatMessage[]
  sections: Array<{ id: string; title: string; word_count?: number }>
  chunk_count: number
}

const router = useRouter()
const PREFERENCES_KEY = 'reading-copilot.preferences'
const DEEP_READ_SEED_KEY = 'reading-copilot:deep-read-seed'
const DEEP_QA_SEED_KEY = 'reading-copilot:deep-qa-seed'

marked.setOptions({ breaks: true, gfm: true })

const showImportDialog = ref(false)
const showSessions = ref(false)
const importMode = ref<'text' | 'pdf'>('text')
const importText = ref('')
const selectedImportFile = ref<File | null>(null)
const isImporting = ref(false)
const currentSessionId = ref('')
const sessionData = ref<SessionData | null>(null)
const sessions = ref<any[]>([])
const renderedMarkdown = ref('')
const currentTheme = ref<'light' | 'paper' | 'dark'>('light')
const fontSize = ref(16)
const lineHeight = ref(1.9)
const viewMode = ref<'formatted' | 'raw'>('formatted')
const activeLens = ref<'all' | 'data' | 'entity' | 'logic'>('all')
const activeTab = ref<'guide' | 'podcast' | 'graph' | 'chat'>('guide')
const leftSidebarTab = ref<'toc' | 'sections'>('toc')
const chatMessages = ref<ChatMessage[]>([])
const userInput = ref('')
const isStreaming = ref(false)
const streamingContent = ref('')
const streamingMeta = ref<{ references: QuoteAnchor[]; quote_anchor: QuoteAnchor | null }>({
  references: [],
  quote_anchor: null,
})
const pendingQuoteText = ref('')
const pendingQuoteAnchor = ref<QuoteAnchor | null>(null)
const showSelectionMenu = ref(false)
const menuPosition = ref({ x: 0, y: 0 })
const selectedText = ref('')
const selectedAnchor = ref<QuoteAnchor | null>(null)
const readingProgress = ref(0)
const currentSectionId = ref('')

const readingAreaRef = ref<HTMLElement | null>(null)
const chatMessagesRef = ref<HTMLElement | null>(null)
const graphRef = ref<HTMLElement | null>(null)
const uploadRef = ref<any>(null)

let graphInstance: echarts.ECharts | null = null

const themeClass = computed(() => `theme-${currentTheme.value}`)
const readingAreaClasses = computed(() => [`view-${viewMode.value}`, `lens-mode-${activeLens.value}`])
const tableOfContents = computed(() => {
  const sections = sessionData.value?.sections || sessionData.value?.summary_data?.sections || []
  return sections.map((section: any) => ({
    id: section.id,
    text: section.title,
    word_count: section.word_count,
  }))
})
const sectionSummaries = computed(() => sessionData.value?.summary_data?.section_summaries || [])
const openQuestions = computed(() => sessionData.value?.summary_data?.open_questions || [])
const guideClaims = computed(() => sessionData.value?.summary_data?.argument_map?.claims || [])
const guideTensions = computed(() => sessionData.value?.summary_data?.argument_map?.tensions || [])
const quickQuestions = computed(() => {
  const sectionQuestions = sectionSummaries.value
    .map((item: any) => item.question)
    .filter(Boolean)
    .slice(0, 2)
  return [...openQuestions.value.slice(0, 2), ...sectionQuestions].slice(0, 4)
})
const currentSectionTitle = computed(() => {
  const match = tableOfContents.value.find(item => item.id === currentSectionId.value)
  return match?.text || ''
})

function sanitizeHtml(html: string) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const allowedTags = new Set(['a', 'blockquote', 'br', 'code', 'em', 'h2', 'h3', 'hr', 'li', 'mark', 'ol', 'p', 'pre', 'strong', 'ul'])
  const allowedAttributes: Record<string, string[]> = {
    a: ['href', 'target', 'rel'],
    h2: ['id'],
    mark: ['class'],
    code: ['class'],
  }

  const walk = (node: Node) => {
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === Node.COMMENT_NODE) {
        child.parentNode?.removeChild(child)
        continue
      }

      if (child.nodeType !== Node.ELEMENT_NODE) {
        continue
      }

      const el = child as HTMLElement
      const tag = el.tagName.toLowerCase()
      if (!allowedTags.has(tag)) {
        if (['script', 'style', 'iframe', 'object'].includes(tag)) {
          el.remove()
          continue
        }
        while (el.firstChild) {
          node.insertBefore(el.firstChild, el)
        }
        el.remove()
        continue
      }

      for (const attr of Array.from(el.attributes)) {
        const allowed = allowedAttributes[tag] || []
        if (!allowed.includes(attr.name)) {
          el.removeAttribute(attr.name)
          continue
        }
        if (attr.name === 'href' && !/^(https?:|mailto:)/.test(attr.value)) {
          el.removeAttribute(attr.name)
        }
        if (tag === 'mark' && attr.name === 'class' && !['lens-data', 'lens-entity', 'lens-logic'].includes(attr.value)) {
          el.removeAttribute(attr.name)
        }
        if (tag === 'code' && attr.name === 'class' && !attr.value.startsWith('language-')) {
          el.removeAttribute(attr.name)
        }
      }

      if (tag === 'a') {
        el.setAttribute('target', '_blank')
        el.setAttribute('rel', 'noopener noreferrer')
      }
      walk(el)
    }
  }

  walk(doc.body)
  return doc.body.innerHTML
}

function renderMarkdownToHtml(text: string) {
  return sanitizeHtml(marked(text || '') as string)
}

function renderMessageMarkdown(text: string) {
  return renderMarkdownToHtml(text || '')
}

function savePreferences() {
  localStorage.setItem(PREFERENCES_KEY, JSON.stringify({
    theme: currentTheme.value,
    fontSize: fontSize.value,
    lineHeight: lineHeight.value,
    viewMode: viewMode.value,
    activeLens: activeLens.value,
  }))
}

function loadPreferences() {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    currentTheme.value = parsed.theme || 'light'
    fontSize.value = parsed.fontSize || 16
    lineHeight.value = parsed.lineHeight || 1.9
    viewMode.value = parsed.viewMode || 'formatted'
    activeLens.value = parsed.activeLens || 'all'
  } catch {
    // ignore malformed preferences
  }
}

function sessionScrollKey(sessionId: string) {
  return `reading-copilot:scroll:${sessionId}`
}

function normalizeMessage(msg: any): ChatMessage {
  return {
    role: msg.role,
    content: msg.content || '',
    quote_text: msg.quote_text || '',
    quote_anchor: msg.quote_anchor || null,
    references: msg.references || [],
  }
}

async function initCopilot() {
  isImporting.value = true
  try {
    let res: any
    if (importMode.value === 'text') {
      if (!importText.value.trim()) {
        ElMessage.warning('请输入文本内容')
        return
      }
      res = await apiClient.post('/api/copilot/init', { raw_text: importText.value })
    } else {
      if (!selectedImportFile.value) {
        ElMessage.warning('请先选择 PDF 文件')
        return
      }

      const formData = new FormData()
      formData.append('file', selectedImportFile.value)
      res = await apiClient.post('/api/copilot/init_pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    }

    if (res.success) {
      ElMessage.success(importMode.value === 'pdf' ? 'PDF 处理成功' : '文本处理成功')
      closeImportDialog()
      await loadSession(res.session_id)
      await loadSessions()
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '处理失败')
  } finally {
    isImporting.value = false
  }
}

function handleImportFileChange(file: any) {
  const raw = file?.raw as File | undefined
  if (!raw) return
  if (raw.type !== 'application/pdf' && !raw.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.error('请选择 PDF 文件')
    uploadRef.value?.clearFiles()
    selectedImportFile.value = null
    return
  }
  selectedImportFile.value = raw
}

function handleImportFileRemove() {
  selectedImportFile.value = null
}

function closeImportDialog() {
  showImportDialog.value = false
  importText.value = ''
  importMode.value = 'text'
  selectedImportFile.value = null
  uploadRef.value?.clearFiles?.()
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

async function loadSession(sessionId: string) {
  currentSessionId.value = sessionId
  showSessions.value = false

  try {
    const res: any = await apiClient.get(`/api/copilot/session/${sessionId}`)
    if (!res.success) return

    sessionData.value = res.data
    chatMessages.value = (res.data.messages || []).map(normalizeMessage)
    renderedMarkdown.value = renderMarkdownToHtml(res.data.markdown_content || '')
    activeTab.value = 'guide'
    leftSidebarTab.value = 'toc'

    await nextTick()
    assignHeadingIds()
    restoreReadingPosition()
    updateReadingProgress()
    renderKnowledgeGraph()
    scrollToBottom()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载会话失败')
  }
}

function assignHeadingIds() {
  const headings = Array.from(readingAreaRef.value?.querySelectorAll('.markdown-content h2') || [])
  headings.forEach((heading, index) => {
    const section = tableOfContents.value[index]
    if (!section) return
    ;(heading as HTMLElement).id = section.id
  })
}

async function scrollToHeading(id: string) {
  if (viewMode.value !== 'formatted') {
    viewMode.value = 'formatted'
    await nextTick()
    assignHeadingIds()
  }

  const target = document.getElementById(id)
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function scrollToAnchor(anchor?: QuoteAnchor | null) {
  if (!anchor?.section_id) return
  await scrollToHeading(anchor.section_id)
}

function adjustFontSize(delta: number) {
  fontSize.value = Math.max(13, Math.min(24, fontSize.value + delta))
}

function clampMenuPosition(x: number, y: number) {
  const maxX = Math.max(16, window.innerWidth - 380)
  const maxY = Math.max(16, window.innerHeight - 100)
  return {
    x: Math.min(Math.max(16, x), maxX),
    y: Math.min(Math.max(16, y), maxY),
  }
}

function getAnchorByRange(range: Range): QuoteAnchor | null {
  const contentEl = readingAreaRef.value?.querySelector('.markdown-content')
  if (!contentEl) return null
  const rect = range.getBoundingClientRect()
  const top = rect.top - (readingAreaRef.value?.getBoundingClientRect().top || 0) + (readingAreaRef.value?.scrollTop || 0)
  const headings = Array.from(contentEl.querySelectorAll('h2[id]')) as HTMLElement[]
  const current = headings.filter(el => el.offsetTop <= top + 8).pop()
  if (!current) return null
  return {
    section_id: current.id,
    section_title: current.textContent || '',
  }
}

function handleTextSelection() {
  const selection = window.getSelection()
  const text = selection?.toString().trim() || ''
  if (!text || !readingAreaRef.value?.contains(selection?.anchorNode || null)) {
    return
  }

  selectedText.value = text
  const range = selection?.rangeCount ? selection.getRangeAt(0) : null
  selectedAnchor.value = range ? getAnchorByRange(range) : null

  if (range) {
    const rect = range.getBoundingClientRect()
    menuPosition.value = clampMenuPosition(
      rect.left + rect.width / 2 - 170,
      rect.top - 56
    )
    showSelectionMenu.value = true
  }
}

function hideSelectionMenu() {
  showSelectionMenu.value = false
}

function clearSelection() {
  window.getSelection()?.removeAllRanges()
  selectedText.value = ''
  selectedAnchor.value = null
}

function clearPendingQuote() {
  pendingQuoteText.value = ''
  pendingQuoteAnchor.value = null
}

function quoteSelection() {
  if (!selectedText.value) return
  pendingQuoteText.value = selectedText.value
  pendingQuoteAnchor.value = selectedAnchor.value
  activeTab.value = 'chat'
  hideSelectionMenu()
  clearSelection()
}

function getActionLabel(action: string) {
  const labels: Record<string, string> = {
    explain: '请解释这段内容',
    translate: '请翻译这段内容',
    summarize: '请总结这段内容',
    explain_5yr: '请用 5 岁小孩能懂的方式解释这段内容',
    extract_quote: '请把这段内容提炼成一句金句',
    feynman_quiz: '请反过来考考我',
  }
  return labels[action] || action
}

async function streamCopilotMessage(payload: {
  query: string
  action: string
  quoteText?: string
  quoteAnchor?: QuoteAnchor | null
  userDisplay?: string
}) {
  if (!currentSessionId.value) return

  isStreaming.value = true
  streamingContent.value = ''
  streamingMeta.value = { references: [], quote_anchor: payload.quoteAnchor || null }

  chatMessages.value.push({
    role: 'user',
    content: payload.userDisplay || payload.query || '围绕引用继续发问',
    quote_text: payload.quoteText || '',
    quote_anchor: payload.quoteAnchor || null,
  })

  await nextTick()
  scrollToBottom()

  const baseUrl = apiClient.defaults.baseURL || ''

  try {
    const res = await fetch(`${baseUrl}/api/copilot/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: currentSessionId.value,
        query: payload.query,
        quote_text: payload.quoteText || '',
        quote_anchor: payload.quoteAnchor || null,
        action: payload.action,
      }),
    })

    if (!res.ok || !res.body) {
      throw new Error('无法建立伴读流式连接')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalMessage: ChatMessage | null = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''

      for (const block of blocks) {
        if (!block.startsWith('data: ')) continue
        const raw = block.slice(6)
        const parsed = JSON.parse(raw)

        if (parsed.type === 'meta') {
          streamingMeta.value = {
            references: parsed.references || [],
            quote_anchor: parsed.quote_anchor || payload.quoteAnchor || null,
          }
        } else if (parsed.type === 'chunk') {
          streamingContent.value += parsed.content || ''
          await nextTick()
          scrollToBottom()
        } else if (parsed.type === 'done') {
          finalMessage = normalizeMessage({
            ...parsed.message,
            content: parsed.message?.content || streamingContent.value,
            references: parsed.message?.references || streamingMeta.value.references,
          })
        } else if (parsed.type === 'error') {
          throw new Error(parsed.message || '伴读回答失败')
        }
      }
    }

    chatMessages.value.push(finalMessage || {
      role: 'assistant',
      content: streamingContent.value,
      quote_text: payload.quoteText || '',
      quote_anchor: payload.quoteAnchor || null,
      references: streamingMeta.value.references,
    })
    await loadSessions()
  } catch (e: any) {
    ElMessage.error(e.message || '请求失败')
  } finally {
    isStreaming.value = false
    streamingContent.value = ''
    streamingMeta.value = { references: [], quote_anchor: null }
    clearSelection()
  }
}

async function executeAction(action: string) {
  if (!selectedText.value && action !== 'feynman_quiz') {
    ElMessage.warning('请先选中一段内容')
    return
  }

  hideSelectionMenu()
  activeTab.value = 'chat'
  await streamCopilotMessage({
    query: getActionLabel(action),
    action,
    quoteText: selectedText.value,
    quoteAnchor: selectedAnchor.value,
    userDisplay: getActionLabel(action),
  })
}

async function sendMessage() {
  const quoteText = pendingQuoteText.value
  const quoteAnchor = pendingQuoteAnchor.value
  const query = userInput.value.trim() || (quoteText ? '请结合上下文帮我拆解这段内容' : '')
  if (!query) return

  userInput.value = ''
  clearPendingQuote()
  activeTab.value = 'chat'

  await streamCopilotMessage({
    query,
    action: 'question',
    quoteText,
    quoteAnchor,
    userDisplay: query,
  })
}

function useSuggestedQuestion(question: string) {
  activeTab.value = 'chat'
  userInput.value = question
}

async function runArticleQuiz() {
  activeTab.value = 'chat'
  await streamCopilotMessage({
    query: '请考考我，看我是不是真的读懂了这篇文章',
    action: 'feynman_quiz',
    userDisplay: '请考考我',
  })
}

function jumpToClaim(sectionId?: string) {
  if (!sectionId) return
  scrollToHeading(sectionId)
}

function scrollToBottom() {
  if (!chatMessagesRef.value) return
  chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
}

async function loadSessions() {
  try {
    const res: any = await apiClient.get('/api/copilot/sessions')
    if (res.success) {
      sessions.value = res.data || []
      if (!currentSessionId.value && sessions.value.length > 0) {
        await loadSession(sessions.value[0].id)
      }
    }
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

function handleReadingScroll() {
  if (!currentSessionId.value || !readingAreaRef.value) return
  localStorage.setItem(sessionScrollKey(currentSessionId.value), String(readingAreaRef.value.scrollTop))
  updateReadingProgress()
}

function restoreReadingPosition() {
  if (!currentSessionId.value || !readingAreaRef.value) return
  const saved = Number(localStorage.getItem(sessionScrollKey(currentSessionId.value)) || 0)
  readingAreaRef.value.scrollTop = saved
}

function updateReadingProgress() {
  if (!readingAreaRef.value) return
  const area = readingAreaRef.value
  const total = Math.max(1, area.scrollHeight - area.clientHeight)
  readingProgress.value = Math.min(100, (area.scrollTop / total) * 100)

  if (viewMode.value !== 'formatted') return
  const headings = Array.from(area.querySelectorAll('.markdown-content h2[id]')) as HTMLElement[]
  if (!headings.length) return
  const current = headings.filter(el => el.offsetTop <= area.scrollTop + 60).pop() || headings[0]
  currentSectionId.value = current.id
}

function formatTime(timeStr: string) {
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function openInDeepRead() {
  if (!sessionData.value) return
  localStorage.setItem(DEEP_READ_SEED_KEY, JSON.stringify({
    title: sessionData.value.title,
    text: sessionData.value.raw_text_content || sessionData.value.markdown_content,
  }))
  router.push('/deep-read')
}

function openInDeepQA(question?: string) {
  if (!sessionData.value) return
  localStorage.setItem(DEEP_QA_SEED_KEY, JSON.stringify({
    title: `${sessionData.value.title} / 深挖`,
    topic: sessionData.value.summary_data?.summary || sessionData.value.title,
    question: question || userInput.value || selectedText.value || '这篇文章最值得继续深挖的问题是什么？',
  }))
  router.push('/deep-qa')
}

function renderKnowledgeGraph() {
  const graph = sessionData.value?.summary_data?.knowledge_graph
  if (!graphRef.value || activeTab.value !== 'graph') return
  if (!graph?.nodes?.length) {
    graphInstance?.dispose()
    graphInstance = null
    return
  }

  if (!graphInstance) {
    graphInstance = echarts.init(graphRef.value)
  }

  const categoryColors: Record<string, string> = {
    核心概念: '#2f6fed',
    人物: '#d96c2b',
    机构: '#2f8f5b',
    事件: '#9b4de0',
    数据: '#cc455e',
  }

  graphInstance.setOption({
    animationDuration: 500,
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        force: {
          repulsion: 220,
          edgeLength: 110,
        },
        label: {
          show: true,
          position: 'right',
          formatter: '{b}',
          fontSize: 12,
        },
        lineStyle: {
          color: '#98a2b3',
          width: 1.2,
        },
        edgeLabel: {
          show: true,
          formatter: (params: any) => params.data.label || '',
          fontSize: 11,
          color: '#667085',
        },
        data: graph.nodes.map((node: any) => ({
          ...node,
          symbolSize: node.category === '核心概念' ? 52 : 38,
          itemStyle: {
            color: categoryColors[node.category] || '#5b7c99',
          },
        })),
        links: graph.edges || [],
      },
    ],
  })

  graphInstance.off('click')
  graphInstance.on('click', (params: any) => {
    if (params.dataType !== 'node' || !params.data?.name) return
    activeTab.value = 'chat'
    userInput.value = `文中“${params.data.name}”和全文主线是什么关系？`
  })
}

function handleResize() {
  graphInstance?.resize()
}

watch([currentTheme, fontSize, lineHeight, viewMode, activeLens], savePreferences)

watch(showImportDialog, value => {
  if (!value && !isImporting.value) {
    importText.value = ''
    importMode.value = 'text'
    selectedImportFile.value = null
    uploadRef.value?.clearFiles?.()
  }
})

watch(viewMode, async mode => {
  await nextTick()
  if (mode === 'formatted') {
    assignHeadingIds()
    updateReadingProgress()
  }
})

watch([activeTab, sessionData], async () => {
  if (activeTab.value !== 'graph') return
  await nextTick()
  renderKnowledgeGraph()
})

onMounted(async () => {
  loadPreferences()
  await loadSessions()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  graphInstance?.dispose()
  graphInstance = null
})
</script>

<style scoped>
.reading-copilot {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-color);
  color: var(--text-color);
  transition: background 0.25s ease, color 0.25s ease;
}

.theme-light {
  --bg-color: #f7f8fb;
  --text-color: #223142;
  --sidebar-bg: #ffffff;
  --reading-bg: #fdfdfc;
  --border-color: #dde3ea;
  --accent-soft: rgba(47, 111, 237, 0.08);
}

.theme-paper {
  --bg-color: #efe5d2;
  --text-color: #4b3f31;
  --sidebar-bg: #f6ecda;
  --reading-bg: #fbf4e6;
  --border-color: #d9cab1;
  --accent-soft: rgba(171, 118, 34, 0.12);
}

.theme-dark {
  --bg-color: #101418;
  --text-color: #ecf1f6;
  --sidebar-bg: #16202b;
  --reading-bg: #11181f;
  --border-color: #263342;
  --accent-soft: rgba(102, 163, 255, 0.12);
}

.top-bar {
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--sidebar-bg);
  flex-wrap: wrap;
}

.top-bar-left,
.top-bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(230px, 20%) minmax(0, 1fr) minmax(340px, 30%);
  min-height: 0;
}

.sidebar-left,
.sidebar-right {
  min-height: 0;
  background: var(--sidebar-bg);
}

.sidebar-left {
  border-right: 1px solid var(--border-color);
}

.sidebar-right {
  border-left: 1px solid var(--border-color);
}

.sidebar-left :deep(.el-tabs),
.sidebar-right :deep(.el-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-left :deep(.el-tabs__content),
.sidebar-right :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.sidebar-left :deep(.el-tab-pane),
.sidebar-right :deep(.el-tab-pane) {
  height: 100%;
}

.toc-list,
.section-cards {
  height: 100%;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.toc-item,
.session-item,
.question-chip,
.quick-question {
  border: 0;
  font: inherit;
}

.toc-item {
  text-align: left;
  padding: 12px;
  border-radius: 12px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  border: 1px solid transparent;
}

.toc-item:hover,
.toc-item.active {
  background: var(--accent-soft);
  border-color: var(--border-color);
}

.toc-title {
  display: block;
  font-weight: 600;
  margin-bottom: 4px;
}

.toc-meta {
  font-size: 12px;
  opacity: 0.7;
}

.section-card {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.35);
}

.theme-dark .section-card {
  background: rgba(255, 255, 255, 0.02);
}

.section-card.active {
  box-shadow: 0 0 0 1px rgba(47, 111, 237, 0.2);
}

.section-card-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.section-card-header h4 {
  margin: 0;
  font-size: 15px;
}

.section-card p,
.section-card li {
  line-height: 1.6;
}

.section-card ul {
  margin: 10px 0 0;
  padding-left: 18px;
}

.section-question {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--accent-soft);
  font-size: 13px;
}

.section-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.reading-area {
  position: relative;
  overflow-y: auto;
  padding: 22px 48px 48px;
  background: linear-gradient(180deg, var(--reading-bg) 0%, rgba(255, 255, 255, 0.82) 100%);
}

.theme-dark .reading-area {
  background: linear-gradient(180deg, var(--reading-bg) 0%, rgba(17, 24, 31, 0.92) 100%);
}

.reading-progress-shell {
  position: sticky;
  top: 0;
  z-index: 4;
  height: 4px;
  background: rgba(128, 128, 128, 0.12);
  border-radius: 999px;
  overflow: hidden;
}

.reading-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #2f6fed, #4fb286);
  border-radius: inherit;
}

.reading-status {
  position: sticky;
  top: 10px;
  z-index: 4;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  margin: 12px auto 18px;
  max-width: 860px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  font-size: 13px;
}

.theme-dark .reading-status {
  background: rgba(17, 24, 31, 0.78);
}

.markdown-content,
.raw-content {
  max-width: 820px;
  margin: 0 auto;
}

.raw-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.reading-area :deep(.markdown-content h2) {
  margin: 38px 0 18px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--border-color);
  font-size: 26px;
  line-height: 1.3;
}

.reading-area :deep(.markdown-content h3) {
  margin: 22px 0 12px;
}

.reading-area :deep(.markdown-content p),
.raw-content {
  margin: 0 0 1.3em;
}

.reading-area :deep(.markdown-content blockquote) {
  margin: 0 0 1.3em;
  padding: 12px 16px;
  border-left: 4px solid #2f6fed;
  background: var(--accent-soft);
  border-radius: 0 12px 12px 0;
}

.reading-area :deep(mark.lens-data),
.reading-area :deep(mark.lens-entity),
.reading-area :deep(mark.lens-logic) {
  border-radius: 6px;
  padding: 0 4px;
  transition: all 0.2s ease;
}

.reading-area :deep(mark.lens-data) {
  background: rgba(209, 65, 85, 0.18);
  box-shadow: inset 0 -1px 0 rgba(209, 65, 85, 0.2);
}

.reading-area :deep(mark.lens-entity) {
  background: rgba(47, 111, 237, 0.16);
  box-shadow: inset 0 -1px 0 rgba(47, 111, 237, 0.18);
}

.reading-area :deep(mark.lens-logic) {
  background: rgba(75, 176, 119, 0.18);
  box-shadow: inset 0 -1px 0 rgba(75, 176, 119, 0.2);
}

.reading-area.lens-mode-data :deep(mark.lens-entity),
.reading-area.lens-mode-data :deep(mark.lens-logic),
.reading-area.lens-mode-entity :deep(mark.lens-data),
.reading-area.lens-mode-entity :deep(mark.lens-logic),
.reading-area.lens-mode-logic :deep(mark.lens-data),
.reading-area.lens-mode-logic :deep(mark.lens-entity) {
  background: transparent;
  box-shadow: none;
  opacity: 0.35;
}

.guide-card,
.podcast-card,
.graph-card {
  height: 100%;
  overflow-y: auto;
  padding: 18px;
}

.hero-summary {
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(47, 111, 237, 0.13), rgba(79, 178, 134, 0.09));
  border: 1px solid var(--border-color);
}

.hero-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  opacity: 0.7;
  margin-bottom: 8px;
}

.hero-summary p {
  margin: 0;
  line-height: 1.7;
}

.guide-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.guide-section {
  margin-top: 20px;
}

.guide-section h4 {
  margin: 0 0 10px;
}

.guide-section ul {
  margin: 0;
  padding-left: 18px;
}

.guide-section li {
  margin-bottom: 8px;
  line-height: 1.6;
}

.claim-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.claim-card {
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 14px;
}

.claim-text {
  margin: 0 0 8px;
  font-weight: 600;
}

.claim-evidence {
  margin: 0;
  line-height: 1.6;
  opacity: 0.82;
}

.claim-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.question-chips,
.quick-question-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.question-chip,
.quick-question {
  padding: 10px 12px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: inherit;
  cursor: pointer;
}

.question-chip:hover,
.quick-question:hover {
  transform: translateY(-1px);
}

.meta-info {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
  font-size: 13px;
}

.meta-info span {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--accent-soft);
}

.podcast-turn {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  margin-bottom: 12px;
}

.podcast-turn.host {
  background: rgba(47, 111, 237, 0.06);
}

.podcast-turn.guest {
  background: rgba(79, 178, 134, 0.06);
}

.speaker {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.podcast-turn p {
  margin: 0;
  line-height: 1.7;
}

.knowledge-graph {
  height: 380px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
}

.graph-hint {
  margin-top: 12px;
  font-size: 13px;
  opacity: 0.72;
}

.chat-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-item {
  max-width: 92%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-item.user {
  align-self: flex-end;
}

.message-item.assistant {
  align-self: flex-start;
}

.quote-text {
  padding: 10px 12px;
  border-left: 3px solid #4fb286;
  border-radius: 0 12px 12px 0;
  background: rgba(79, 178, 134, 0.08);
}

.quote-text.clickable {
  cursor: pointer;
}

.quote-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.quote-label {
  font-size: 12px;
  font-weight: 700;
  color: #2f8f5b;
}

.quote-jump {
  font-size: 12px;
  opacity: 0.75;
}

.quote-text p {
  margin: 0;
  line-height: 1.5;
  font-size: 13px;
}

.message-content {
  padding: 12px 14px;
  border-radius: 18px;
  line-height: 1.6;
}

.user-text {
  background: #2f6fed;
  color: white;
  border-bottom-right-radius: 6px;
}

.assistant-markdown {
  background: rgba(255, 255, 255, 0.72);
  color: inherit;
  border-bottom-left-radius: 6px;
  border: 1px solid var(--border-color);
}

.theme-dark .assistant-markdown {
  background: rgba(255, 255, 255, 0.03);
}

.assistant-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.cursor {
  color: #2f6fed;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.chat-input-area {
  border-top: 1px solid var(--border-color);
  padding: 16px;
  background: var(--sidebar-bg);
}

.pending-quote {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(250, 173, 20, 0.12);
  margin-bottom: 12px;
  font-size: 13px;
}

.quick-question-row {
  margin-bottom: 12px;
}

.quick-question {
  text-align: left;
}

.chat-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.selection-menu {
  position: fixed;
  z-index: 9999;
  background: #1d2939;
  padding: 6px;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
  display: flex;
  gap: 4px;
}

.selection-menu .el-button {
  background: transparent;
  border: 0;
  color: #f8fafc;
}

.selection-menu .el-button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.import-upload {
  width: 100%;
}

.selected-file-card {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--accent-soft);
}

.selected-file-name {
  font-weight: 600;
  margin-bottom: 4px;
}

.selected-file-meta {
  font-size: 12px;
  opacity: 0.76;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.session-item {
  width: 100%;
  text-align: left;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--sidebar-bg);
  color: inherit;
  cursor: pointer;
}

.session-item:hover,
.session-item.active {
  background: var(--accent-soft);
}

.session-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  opacity: 0.75;
}

@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 260px minmax(0, 1fr);
  }

  .sidebar-right {
    grid-column: 1 / -1;
    border-left: 0;
    border-top: 1px solid var(--border-color);
    min-height: 420px;
  }
}

@media (max-width: 860px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .sidebar-left {
    display: none;
  }

  .reading-area {
    padding: 16px 18px 26px;
  }

  .sidebar-right {
    min-height: 380px;
  }
}
</style>
