<template>
  <div class="reading-copilot" :class="themeClass">
    <div class="top-bar">
      <div class="top-bar-left">
        <el-button @click="showImportDialog = true" type="primary" :icon="Plus">导入长文本</el-button>
        <el-button @click="showSessions = !showSessions" :icon="List">历史项目</el-button>
        <el-button
          v-if="currentSessionId"
          plain
          :icon="Download"
          :loading="isExporting"
          @click="downloadSessionMarkdown"
        >
          导出 Markdown
        </el-button>
      </div>

      <div class="top-bar-right" v-if="currentSessionId">
        <div class="top-stat-pill">
          <span>进度 {{ Math.round(readingProgress) }}%</span>
          <span>{{ sessionData?.word_count || 0 }} 字</span>
          <span>{{ sessionData?.read_time || 0 }} 分钟</span>
        </div>

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
      <aside class="left-rail">
        <div class="rail-scroll">
          <section class="panel-card overview-card">
            <div class="eyebrow">AI 伴读总览</div>
            <h2>{{ sessionData?.title || '长文伴读' }}</h2>
            <p class="overview-summary">{{ sessionData?.summary_data?.summary || '正在整理导读...' }}</p>

            <div class="metric-row">
              <div class="metric-pill">
                <span class="metric-label">当前章节</span>
                <strong>{{ currentSectionTitle || '从开头开始' }}</strong>
              </div>
              <div class="metric-pill">
                <span class="metric-label">阅读耗时</span>
                <strong>{{ sessionData?.read_time || 0 }} 分钟</strong>
              </div>
            </div>

            <div class="reading-progress-shell compact">
              <div class="reading-progress-bar" :style="{ width: `${readingProgress}%` }"></div>
            </div>
          </section>

          <section class="panel-card" v-if="hasStudyGuide">
            <div class="section-head">
              <h3>阅读路线</h3>
              <span>按这个顺序更容易读懂</span>
            </div>

            <div class="guide-grid">
              <article class="guide-step" v-if="studyGuide.before_reading?.length">
                <div class="guide-label">开始前先抓</div>
                <ul>
                  <li v-for="item in studyGuide.before_reading" :key="item">{{ item }}</li>
                </ul>
              </article>

              <article class="guide-step" v-if="studyGuide.while_reading?.length">
                <div class="guide-label">阅读时留意</div>
                <ul>
                  <li v-for="item in studyGuide.while_reading" :key="item">{{ item }}</li>
                </ul>
              </article>

              <article class="guide-step" v-if="studyGuide.after_reading?.length">
                <div class="guide-label">读完后检验</div>
                <ul>
                  <li v-for="item in studyGuide.after_reading" :key="item">{{ item }}</li>
                </ul>
              </article>
            </div>
          </section>

          <section class="panel-card">
            <div class="section-head">
              <h3>章节地图</h3>
              <span>{{ sectionCards.length }} 节</span>
            </div>

            <div class="section-list">
              <button
                v-for="section in sectionCards"
                :key="section.id"
                class="section-link"
                :class="{ active: section.id === currentSectionId }"
                @click="scrollToHeading(section.id)"
              >
                <div class="section-link-top">
                  <strong>{{ section.title }}</strong>
                  <span>{{ section.word_count || 0 }} 字</span>
                </div>
                <p v-if="section.summary">{{ section.summary }}</p>
                <div class="section-link-meta">
                  {{ section.role_in_article || section.question || '点击跳到这一节继续阅读' }}
                </div>
              </button>
            </div>
          </section>
        </div>
      </aside>

      <main
        class="reading-stage"
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

        <div class="reading-stage-header">
          <div class="stage-title">
            <div class="eyebrow">当前在读</div>
            <h1>{{ currentSectionTitle || sessionData?.title || '准备开始阅读' }}</h1>
          </div>
          <div class="stage-meta">
            <span>阅读进度 {{ Math.round(readingProgress) }}%</span>
            <span>字号 {{ fontSize }}</span>
          </div>
        </div>

        <section v-if="currentSectionSummary" class="focus-card">
          <div class="focus-grid">
            <div class="focus-item">
              <span class="focus-label">这节在讲什么</span>
              <p>{{ currentSectionSummary.summary || '这一节的摘要还在整理中。' }}</p>
            </div>
            <div class="focus-item">
              <span class="focus-label">它在全文中的作用</span>
              <p>{{ currentSectionSummary.role_in_article || '先看它怎么承接上文、推进结论。' }}</p>
            </div>
          </div>

          <div class="soft-chip-row">
            <button
              class="soft-chip"
              @click="useSuggestedQuestion(`这一节《${currentSectionSummary.title}》在全文里起什么作用？`)"
            >
              问这节的作用
            </button>
            <button
              class="soft-chip"
              @click="useSuggestedQuestion(`这一节《${currentSectionSummary.title}》最值得怀疑的前提是什么？`)"
            >
              找隐含前提
            </button>
            <button
              v-if="currentSectionSummary.question"
              class="soft-chip"
              @click="useSuggestedQuestion(currentSectionSummary.question)"
            >
              继续追问这节
            </button>
          </div>
        </section>

        <div v-if="viewMode === 'formatted'" v-html="renderedMarkdown" class="markdown-content"></div>
        <div v-else class="raw-content">{{ sessionData?.raw_text_content || '' }}</div>
      </main>

      <aside class="coach-panel">
        <div class="coach-scroll">
          <section class="panel-card coach-card" v-if="currentSectionSummary">
            <div class="section-head">
              <h3>当前章节陪读</h3>
              <span>{{ currentSectionSummary.word_count || 0 }} 字</span>
            </div>

            <p class="coach-summary">{{ currentSectionSummary.summary }}</p>

            <ul class="bullet-list" v-if="currentSectionSummary.takeaways?.length">
              <li v-for="point in currentSectionSummary.takeaways" :key="point">{{ point }}</li>
            </ul>

            <div class="mini-note" v-if="currentSectionSummary.hidden_assumption">
              <span class="mini-note-label">隐含前提</span>
              <p>{{ currentSectionSummary.hidden_assumption }}</p>
            </div>

            <div class="mini-note" v-if="currentSectionSummary.question">
              <span class="mini-note-label">建议追问</span>
              <p>{{ currentSectionSummary.question }}</p>
              <el-button size="small" type="primary" plain @click="useSuggestedQuestion(currentSectionSummary.question)">直接发问</el-button>
            </div>
          </section>

          <section class="panel-card coach-card">
            <div class="section-head">
              <h3>全文主线</h3>
              <span>{{ sessionData?.chunk_count || 0 }} 段</span>
            </div>

            <ul class="bullet-list" v-if="sessionData?.summary_data?.takeaways?.length">
              <li v-for="point in sessionData?.summary_data?.takeaways || []" :key="point">{{ point }}</li>
            </ul>

            <div class="claim-list" v-if="guideClaims.length">
              <article v-for="(claim, index) in guideClaims.slice(0, 3)" :key="`${claim.claim}-${index}`" class="claim-card">
                <p class="claim-text">{{ claim.claim }}</p>
                <p class="claim-evidence">{{ claim.evidence }}</p>
                <div class="claim-actions">
                  <el-button size="small" @click="jumpToClaim(claim.section_id)">跳回原文</el-button>
                  <el-button size="small" type="primary" plain @click="useSuggestedQuestion(`文中“${claim.claim}”的依据够不够强？`)">继续追问</el-button>
                </div>
              </article>
            </div>

            <div class="mini-note warning" v-if="guideTensions.length">
              <span class="mini-note-label">值得多想一层</span>
              <ul class="bullet-list compact-list">
                <li v-for="item in guideTensions" :key="item">{{ item }}</li>
              </ul>
            </div>

            <div class="soft-chip-row" v-if="openQuestions.length">
              <button
                v-for="question in openQuestions.slice(0, 4)"
                :key="question"
                class="soft-chip"
                @click="useSuggestedQuestion(question)"
              >
                {{ question }}
              </button>
            </div>
          </section>

          <section class="panel-card notes-card">
            <div class="section-head">
              <h3>我的笔记</h3>
              <div class="notes-head-actions">
                <span class="notes-status" :class="{ dirty: notesDirty }">{{ notesDirty ? '未保存' : '已保存' }}</span>
                <el-button size="small" @click="saveReaderNotes" :loading="isSavingNotes" :disabled="!notesDirty">保存</el-button>
              </div>
            </div>

            <el-input
              v-model="readerNotes"
              type="textarea"
              :rows="8"
              placeholder="把你真正学到的东西写下来。导出的 Markdown 会自动带上这些笔记。"
              @input="notesDirty = true"
            />

            <div class="notes-footer">
              <span>建议记下：作者主张、你的质疑、准备带走的行动。</span>
              <el-button size="small" plain :icon="Download" :loading="isExporting" @click="downloadSessionMarkdown">导出到 Obsidian</el-button>
            </div>
          </section>

          <section class="panel-card chat-card">
            <div class="section-head">
              <h3>伴读对话</h3>
              <span>围绕当前章节继续问</span>
            </div>

            <div class="soft-chip-row" v-if="quickQuestions.length">
              <button
                v-for="question in quickQuestions"
                :key="question"
                class="soft-chip"
                @click="useSuggestedQuestion(question)"
              >
                {{ question }}
              </button>
            </div>

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

                <div v-if="msg.references?.length" class="reference-row">
                  <button
                    v-for="ref in msg.references.slice(0, 3)"
                    :key="`${ref.section_id}-${ref.chunk_id}-${ref.preview}`"
                    class="reference-chip"
                    @click="scrollToAnchor(ref)"
                  >
                    {{ ref.section_title || '参考段落' }}
                  </button>
                </div>
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
                  <p>{{ streamingMeta.references[0]?.preview || '助手正在结合相关段落作答...' }}</p>
                </div>
                <div class="message-content assistant-markdown markdown-body" v-html="renderMessageMarkdown(streamingContent) + '<span class=&quot;cursor&quot;>▋</span>'"></div>
                <div v-if="streamingMeta.references.length" class="reference-row">
                  <button
                    v-for="ref in streamingMeta.references.slice(0, 3)"
                    :key="`${ref.section_id}-${ref.chunk_id}-${ref.preview}`"
                    class="reference-chip"
                    @click="scrollToAnchor(ref)"
                  >
                    {{ ref.section_title || '参考段落' }}
                  </button>
                </div>
              </div>
            </div>

            <div class="chat-input-area">
              <div v-if="pendingQuoteText" class="pending-quote">
                <span>{{ pendingQuoteAnchor?.section_title || '引用片段' }}：{{ pendingQuoteText }}</span>
                <el-button @click="clearPendingQuote" type="text" :icon="Close" size="small"></el-button>
              </div>

              <el-input
                v-model="userInput"
                type="textarea"
                :rows="3"
                placeholder="输入你的问题，或者先划词再发问..."
                @keydown.enter.prevent="sendMessage"
              ></el-input>

              <div class="chat-actions">
                <el-button @click="sendMessage" type="primary" :disabled="isStreaming || (!userInput.trim() && !pendingQuoteText)">发送</el-button>
                <el-button plain @click="runArticleQuiz" :disabled="isStreaming">考考我</el-button>
                <el-button plain @click="useSuggestedQuestion('请帮我把这篇文章讲给完全不了解的人听')" :disabled="isStreaming">转述给朋友</el-button>
              </div>
            </div>
          </section>

          <section class="panel-card extra-card">
            <div class="section-head">
              <h3>延伸工具</h3>
              <div class="tool-switcher">
                <button class="tool-chip" :class="{ active: inspectorMode === 'graph' }" @click="inspectorMode = 'graph'">图谱</button>
                <button class="tool-chip" :class="{ active: inspectorMode === 'podcast' }" @click="inspectorMode = 'podcast'">播客</button>
              </div>
            </div>

            <div v-if="inspectorMode === 'graph'" class="tool-panel">
              <div ref="graphRef" class="knowledge-graph"></div>
              <p class="graph-hint">点知识图谱节点，会自动帮你生成一个更具体的追问。</p>
            </div>

            <div v-else class="tool-panel podcast-card">
              <div
                v-for="(item, index) in sessionData?.summary_data?.podcast_script || []"
                :key="`${item.speaker}-${index}`"
                class="podcast-turn"
                :class="item.speaker === 'A' ? 'host' : 'guest'"
              >
                <div class="speaker">{{ item.speaker === 'A' ? '主播 A' : '嘉宾 B' }}</div>
                <p>{{ item.text }}</p>
              </div>
              <el-empty v-if="!(sessionData?.summary_data?.podcast_script || []).length" description="还没有播客脚本" />
            </div>
          </section>
        </div>
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
            <span>{{ session.word_count }} 字 · {{ session.read_time }} 分钟</span>
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
import { Close, Download, List, Minus, Plus, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import apiClient from '@/api'

interface QuoteAnchor {
  chunk_id?: string
  section_id?: string
  section_title?: string
  preview?: string
}

interface SectionSummary {
  id: string
  title: string
  word_count?: number
  summary?: string
  role_in_article?: string
  takeaways?: string[]
  question?: string
  hidden_assumption?: string
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
  created_at?: string
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
const isExporting = ref(false)
const isSavingNotes = ref(false)
const notesDirty = ref(false)
const currentSessionId = ref('')
const sessionData = ref<SessionData | null>(null)
const sessions = ref<any[]>([])
const renderedMarkdown = ref('')
const currentTheme = ref<'light' | 'paper' | 'dark'>('light')
const fontSize = ref(16)
const lineHeight = ref(1.9)
const viewMode = ref<'formatted' | 'raw'>('formatted')
const activeLens = ref<'all' | 'data' | 'entity' | 'logic'>('all')
const inspectorMode = ref<'graph' | 'podcast'>('graph')
const chatMessages = ref<ChatMessage[]>([])
const userInput = ref('')
const readerNotes = ref('')
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
const sectionSummaries = computed<SectionSummary[]>(() => sessionData.value?.summary_data?.section_summaries || [])
const sectionCards = computed<SectionSummary[]>(() => {
  if (sectionSummaries.value.length) return sectionSummaries.value
  return tableOfContents.value.map(item => ({
    id: item.id,
    title: item.text,
    word_count: item.word_count,
    summary: '',
    role_in_article: '',
    takeaways: [],
    question: '',
    hidden_assumption: '',
  }))
})
const studyGuide = computed(() => sessionData.value?.summary_data?.study_guide || {})
const hasStudyGuide = computed(() =>
  ['before_reading', 'while_reading', 'after_reading'].some(key => (studyGuide.value?.[key] || []).length)
)
const openQuestions = computed<string[]>(() => sessionData.value?.summary_data?.open_questions || [])
const guideClaims = computed(() => sessionData.value?.summary_data?.argument_map?.claims || [])
const guideTensions = computed<string[]>(() => sessionData.value?.summary_data?.argument_map?.tensions || [])
const currentSectionTitle = computed(() => {
  const match = tableOfContents.value.find(item => item.id === currentSectionId.value)
  return match?.text || sectionCards.value[0]?.title || ''
})
const currentSectionSummary = computed<SectionSummary | null>(() => {
  return sectionCards.value.find(item => item.id === currentSectionId.value) || sectionCards.value[0] || null
})
const quickQuestions = computed<string[]>(() => {
  const prompts = [
    currentSectionSummary.value?.question,
    currentSectionSummary.value ? `这一节《${currentSectionSummary.value.title}》在全文里起什么作用？` : '',
    '作者最关键的论证链条是什么？',
    ...openQuestions.value,
  ].filter(Boolean) as string[]
  return [...new Set(prompts)].slice(0, 4)
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
    readerNotes.value = res.data.summary_data?.reader_notes || ''
    notesDirty.value = false
    inspectorMode.value = 'graph'

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

  await streamCopilotMessage({
    query,
    action: 'question',
    quoteText,
    quoteAnchor,
    userDisplay: query,
  })
}

function useSuggestedQuestion(question: string) {
  userInput.value = question
}

async function runArticleQuiz() {
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

async function saveReaderNotes(showSuccess = true) {
  if (!currentSessionId.value) return
  if (!notesDirty.value) return

  isSavingNotes.value = true
  try {
    const res: any = await apiClient.post(`/api/copilot/session/${currentSessionId.value}/notes`, {
      content: readerNotes.value,
    })
    if (res.success) {
      notesDirty.value = false
      if (sessionData.value?.summary_data) {
        sessionData.value.summary_data.reader_notes = readerNotes.value
      }
      if (showSuccess) {
        ElMessage.success('笔记已保存')
      }
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '保存笔记失败')
    throw e
  } finally {
    isSavingNotes.value = false
  }
}

function parseFilename(contentDisposition: string | null) {
  const fallback = `${(sessionData.value?.title || '长文伴读').replace(/[\\/:*?"<>|]+/g, '-')}.md`
  if (!contentDisposition) return fallback
  const match = contentDisposition.match(/filename="?([^"]+)"?/)
  return decodeURIComponent(match?.[1] || fallback)
}

async function downloadSessionMarkdown() {
  if (!currentSessionId.value) return
  isExporting.value = true

  try {
    if (notesDirty.value) {
      await saveReaderNotes(false)
    }

    const baseUrl = apiClient.defaults.baseURL || ''
    const res = await fetch(`${baseUrl}/api/copilot/session/${currentSessionId.value}/export_md`)
    if (!res.ok) {
      throw new Error('导出 Markdown 失败')
    }

    const blob = await res.blob()
    const fileName = parseFilename(res.headers.get('content-disposition'))
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('Markdown 已开始下载')
  } catch (e: any) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    isExporting.value = false
  }
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
  if (!graphRef.value || inspectorMode.value !== 'graph') return
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

watch([inspectorMode, sessionData], async () => {
  if (inspectorMode.value !== 'graph') return
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
  --bg-color: #f3f6fb;
  --text-color: #223142;
  --sidebar-bg: rgba(255, 255, 255, 0.82);
  --reading-bg: #fdfcf8;
  --border-color: #dbe3ee;
  --accent-soft: rgba(47, 111, 237, 0.08);
  --accent-strong: #2f6fed;
  --card-shadow: 0 18px 45px rgba(25, 48, 79, 0.07);
}

.theme-paper {
  --bg-color: #e9dfc9;
  --text-color: #4d3d2b;
  --sidebar-bg: rgba(251, 244, 230, 0.8);
  --reading-bg: #faf1e1;
  --border-color: #d7c7ab;
  --accent-soft: rgba(171, 118, 34, 0.12);
  --accent-strong: #ab7622;
  --card-shadow: 0 18px 45px rgba(85, 61, 21, 0.08);
}

.theme-dark {
  --bg-color: #0d141c;
  --text-color: #ebf1f7;
  --sidebar-bg: rgba(21, 31, 43, 0.82);
  --reading-bg: #111821;
  --border-color: #263545;
  --accent-soft: rgba(102, 163, 255, 0.12);
  --accent-strong: #6aa3ff;
  --card-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
}

.top-bar {
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--sidebar-bg);
  backdrop-filter: blur(12px);
  flex-wrap: wrap;
}

.top-bar-left,
.top-bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.top-stat-pill {
  display: flex;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.45);
  font-size: 13px;
}

.theme-dark .top-stat-pill {
  background: rgba(255, 255, 255, 0.04);
}

.main-content {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(260px, 21%) minmax(0, 1fr) minmax(360px, 30%);
}

.left-rail,
.coach-panel {
  min-height: 0;
  background: var(--sidebar-bg);
  backdrop-filter: blur(12px);
}

.left-rail {
  border-right: 1px solid var(--border-color);
}

.coach-panel {
  border-left: 1px solid var(--border-color);
}

.rail-scroll,
.coach-scroll {
  height: 100%;
  overflow-y: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  border: 1px solid var(--border-color);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.52);
  box-shadow: var(--card-shadow);
  padding: 18px;
}

.theme-dark .panel-card {
  background: rgba(255, 255, 255, 0.03);
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.72;
  margin-bottom: 8px;
}

.overview-card h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.overview-summary {
  margin: 14px 0 0;
  line-height: 1.75;
}

.metric-row {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-pill {
  padding: 12px;
  border-radius: 16px;
  background: var(--accent-soft);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.metric-label {
  display: block;
  font-size: 12px;
  opacity: 0.72;
  margin-bottom: 6px;
}

.reading-progress-shell {
  position: sticky;
  top: 0;
  z-index: 4;
  height: 5px;
  background: rgba(128, 128, 128, 0.12);
  border-radius: 999px;
  overflow: hidden;
}

.reading-progress-shell.compact {
  position: relative;
  top: auto;
  margin-top: 16px;
}

.reading-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-strong), #4fb286);
  border-radius: inherit;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-head h3 {
  margin: 0;
  font-size: 17px;
}

.section-head span {
  font-size: 12px;
  opacity: 0.68;
}

.guide-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.guide-step {
  padding: 14px;
  border-radius: 16px;
  background: var(--accent-soft);
}

.guide-label {
  font-weight: 700;
  margin-bottom: 10px;
}

.guide-step ul,
.bullet-list {
  margin: 0;
  padding-left: 18px;
}

.guide-step li,
.bullet-list li {
  margin-bottom: 8px;
  line-height: 1.65;
}

.section-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-link,
.soft-chip,
.tool-chip,
.reference-chip,
.session-item {
  border: 0;
  font: inherit;
}

.section-link {
  width: 100%;
  text-align: left;
  padding: 14px;
  border-radius: 18px;
  background: transparent;
  border: 1px solid transparent;
  color: inherit;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.section-link:hover,
.section-link.active {
  transform: translateY(-1px);
  background: var(--accent-soft);
  border-color: var(--border-color);
}

.section-link-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.section-link-top strong {
  line-height: 1.5;
}

.section-link-top span,
.section-link-meta {
  font-size: 12px;
  opacity: 0.72;
}

.section-link p {
  margin: 10px 0 8px;
  line-height: 1.65;
}

.reading-stage {
  position: relative;
  overflow-y: auto;
  padding: 24px 44px 40px;
  background:
    radial-gradient(circle at top, rgba(96, 163, 255, 0.08), transparent 28%),
    linear-gradient(180deg, var(--reading-bg) 0%, rgba(255, 255, 255, 0.84) 100%);
}

.theme-dark .reading-stage {
  background:
    radial-gradient(circle at top, rgba(106, 163, 255, 0.11), transparent 28%),
    linear-gradient(180deg, var(--reading-bg) 0%, rgba(17, 24, 31, 0.95) 100%);
}

.reading-stage-header {
  position: sticky;
  top: 12px;
  z-index: 4;
  max-width: 900px;
  margin: 14px auto 18px;
  padding: 16px 18px;
  display: flex;
  justify-content: space-between;
  gap: 14px;
  border: 1px solid var(--border-color);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.68);
  backdrop-filter: blur(12px);
}

.theme-dark .reading-stage-header {
  background: rgba(17, 24, 31, 0.76);
}

.stage-title h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.15;
}

.stage-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  opacity: 0.76;
  text-align: right;
}

.focus-card {
  max-width: 900px;
  margin: 0 auto 26px;
  padding: 18px 20px;
  border-radius: 24px;
  background: linear-gradient(135deg, var(--accent-soft), rgba(79, 178, 134, 0.08));
  border: 1px solid var(--border-color);
}

.focus-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.focus-label {
  display: block;
  font-size: 12px;
  opacity: 0.72;
  margin-bottom: 8px;
}

.focus-item p {
  margin: 0;
  line-height: 1.7;
}

.soft-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.soft-chip,
.tool-chip,
.reference-chip {
  padding: 10px 12px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: inherit;
  cursor: pointer;
}

.soft-chip:hover,
.tool-chip:hover,
.reference-chip:hover {
  filter: brightness(0.98);
}

.markdown-content,
.raw-content {
  max-width: 860px;
  margin: 0 auto;
}

.raw-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.reading-stage :deep(.markdown-content h2) {
  margin: 42px 0 18px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--border-color);
  font-size: 27px;
  line-height: 1.3;
}

.reading-stage :deep(.markdown-content h3) {
  margin: 24px 0 12px;
}

.reading-stage :deep(.markdown-content p),
.raw-content {
  margin: 0 0 1.35em;
}

.reading-stage :deep(.markdown-content blockquote) {
  margin: 0 0 1.35em;
  padding: 12px 16px;
  border-left: 4px solid var(--accent-strong);
  background: var(--accent-soft);
  border-radius: 0 12px 12px 0;
}

.reading-stage :deep(mark.lens-data),
.reading-stage :deep(mark.lens-entity),
.reading-stage :deep(mark.lens-logic) {
  border-radius: 6px;
  padding: 0 4px;
  transition: all 0.2s ease;
}

.reading-stage :deep(mark.lens-data) {
  background: rgba(209, 65, 85, 0.18);
  box-shadow: inset 0 -1px 0 rgba(209, 65, 85, 0.2);
}

.reading-stage :deep(mark.lens-entity) {
  background: rgba(47, 111, 237, 0.16);
  box-shadow: inset 0 -1px 0 rgba(47, 111, 237, 0.18);
}

.reading-stage :deep(mark.lens-logic) {
  background: rgba(75, 176, 119, 0.18);
  box-shadow: inset 0 -1px 0 rgba(75, 176, 119, 0.2);
}

.reading-stage.lens-mode-data :deep(mark.lens-entity),
.reading-stage.lens-mode-data :deep(mark.lens-logic),
.reading-stage.lens-mode-entity :deep(mark.lens-data),
.reading-stage.lens-mode-entity :deep(mark.lens-logic),
.reading-stage.lens-mode-logic :deep(mark.lens-data),
.reading-stage.lens-mode-logic :deep(mark.lens-entity) {
  background: transparent;
  box-shadow: none;
  opacity: 0.34;
}

.coach-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.coach-summary,
.claim-evidence,
.mini-note p {
  margin: 0;
  line-height: 1.7;
}

.mini-note {
  padding: 14px;
  border-radius: 16px;
  background: var(--accent-soft);
}

.mini-note.warning {
  background: rgba(210, 87, 87, 0.08);
}

.mini-note-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  opacity: 0.76;
}

.compact-list {
  margin-top: 8px;
}

.claim-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.claim-card {
  border: 1px solid var(--border-color);
  border-radius: 18px;
  padding: 14px;
}

.claim-text {
  margin: 0 0 8px;
  font-weight: 700;
  line-height: 1.6;
}

.claim-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.notes-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notes-status {
  font-size: 12px;
  opacity: 0.72;
}

.notes-status.dirty {
  color: #d96c2b;
  opacity: 1;
}

.notes-card :deep(.el-textarea__inner) {
  min-height: 180px;
  border-radius: 16px;
}

.notes-footer {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  opacity: 0.72;
}

.chat-card {
  min-height: 540px;
}

.chat-messages {
  max-height: 460px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 4px;
}

.message-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-content {
  padding: 14px 16px;
  border-radius: 18px;
  line-height: 1.7;
}

.message-item.user .message-content {
  background: var(--accent-soft);
}

.message-item.assistant .message-content {
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid var(--border-color);
}

.theme-dark .message-item.assistant .message-content {
  background: rgba(255, 255, 255, 0.03);
}

.quote-text {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px dashed var(--border-color);
  background: rgba(255, 255, 255, 0.28);
}

.theme-dark .quote-text {
  background: rgba(255, 255, 255, 0.03);
}

.quote-text.clickable {
  cursor: pointer;
}

.quote-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 12px;
}

.quote-label {
  font-weight: 700;
}

.quote-jump {
  opacity: 0.72;
}

.quote-text p {
  margin: 0;
  line-height: 1.65;
}

.reference-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reference-chip {
  padding: 8px 10px;
  font-size: 12px;
}

.chat-input-area {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pending-quote {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--accent-soft);
}

.chat-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tool-switcher {
  display: flex;
  gap: 8px;
}

.tool-chip.active {
  background: var(--accent-strong);
  color: #fff;
}

.tool-panel {
  min-height: 240px;
}

.knowledge-graph {
  height: 320px;
}

.graph-hint {
  margin: 12px 0 0;
  font-size: 12px;
  opacity: 0.72;
}

.podcast-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.podcast-turn {
  border-radius: 18px;
  padding: 14px;
  border: 1px solid var(--border-color);
  line-height: 1.7;
}

.podcast-turn.host {
  background: rgba(47, 111, 237, 0.08);
}

.podcast-turn.guest {
  background: rgba(79, 178, 134, 0.08);
}

.speaker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
  opacity: 0.76;
}

.empty-state {
  flex: 1;
  display: grid;
  place-items: center;
}

.selection-menu {
  position: fixed;
  z-index: 30;
  display: flex;
  gap: 8px;
  padding: 10px;
  border-radius: 16px;
  background: rgba(17, 24, 31, 0.92);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.24);
}

.selection-menu :deep(.el-button) {
  margin: 0;
}

.selected-file-card {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--accent-soft);
}

.selected-file-name {
  font-weight: 700;
}

.selected-file-meta {
  margin-top: 4px;
  font-size: 12px;
  opacity: 0.72;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  width: 100%;
  text-align: left;
  padding: 14px;
  border-radius: 18px;
  background: transparent;
  color: inherit;
  border: 1px solid transparent;
  cursor: pointer;
}

.session-item:hover,
.session-item.active {
  background: var(--accent-soft);
  border-color: var(--border-color);
}

.session-title {
  font-weight: 700;
}

.session-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  opacity: 0.72;
}

.cursor {
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}

@media (max-width: 1440px) {
  .main-content {
    grid-template-columns: minmax(240px, 26%) minmax(0, 1fr) minmax(330px, 34%);
  }

  .reading-stage {
    padding: 20px 28px 34px;
  }
}

@media (max-width: 1180px) {
  .main-content {
    grid-template-columns: minmax(250px, 280px) minmax(0, 1fr);
  }

  .coach-panel {
    grid-column: 1 / -1;
    border-left: 0;
    border-top: 1px solid var(--border-color);
  }

  .coach-scroll {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .chat-card,
  .extra-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .left-rail,
  .coach-panel {
    border: 0;
  }

  .left-rail {
    border-bottom: 1px solid var(--border-color);
  }

  .coach-scroll {
    grid-template-columns: 1fr;
  }

  .reading-stage {
    padding: 18px 16px 26px;
  }

  .reading-stage-header,
  .focus-grid,
  .metric-row {
    grid-template-columns: 1fr;
  }

  .reading-stage-header {
    flex-direction: column;
  }

  .stage-meta {
    text-align: left;
  }

  .top-bar-right {
    width: 100%;
  }
}
</style>
