<template>
  <div class="card-wrapper">
    <div class="control-panel">
      <el-button type="primary" :loading="isDownloading" @click="downloadCard">
        📸 保存为 1600px 宽幅三栏图
      </el-button>
    </div>
    
    <div id="preview-wrapper" ref="wrapperRef">
      <div id="card-container" ref="cardRef">
        <div class="card-header">
          <span class="card-tag">{{ sourceTag }}</span>
          <h1 class="card-title">{{ title }}</h1>
        </div>
        <div class="card-body" v-html="renderedContent"></div>
        <div class="card-footer">
          DEEPSEEK NEWSROOM · BROADSHEET LAYOUT
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { marked } from 'marked'
import domtoimage from 'dom-to-image-more'

const props = defineProps<{
  title: string
  content: string
  sourceTag: string
}>()

const wrapperRef = ref<HTMLElement | null>(null)
const cardRef = ref<HTMLElement | null>(null)
const isDownloading = ref(false)

const renderedContent = computed(() => {
  return marked(props.content, { breaks: true, gfm: true })
})

const fitPreview = () => {
  if (!wrapperRef.value || !cardRef.value) return
  const wrapper = wrapperRef.value
  const card = cardRef.value
  const scale = wrapper.clientWidth / 1600
  
  card.style.transform = `scale(${scale})`
  wrapper.style.height = (card.offsetHeight * scale) + 'px'
}

onMounted(() => {
  fitPreview()
  window.addEventListener('resize', fitPreview)
  // Wait for fonts
  if ((document as any).fonts) {
    (document as any).fonts.ready.then(fitPreview)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', fitPreview)
})

watch(() => props.content, () => {
  nextTick(fitPreview)
})

const downloadCard = async () => {
  if (!cardRef.value || !wrapperRef.value) return
  isDownloading.value = true
  
  const card = cardRef.value
  const wrapper = wrapperRef.value
  
  // 备份原始样式
  const originalTransform = card.style.transform
  const originalHeight = wrapper.style.height
  
  try {
    // 还原 1:1 真实高度
    card.style.transform = 'none'
    wrapper.style.height = 'auto'
    
    await nextTick()
    
    const exactWidth = 1600
    const exactHeight = card.offsetHeight
    const exportScale = 1.5

    const dataUrl = await domtoimage.toPng(card, {
      width: exactWidth * exportScale,
      height: exactHeight * exportScale,
      style: {
        transform: `scale(${exportScale})`,
        transformOrigin: 'top left',
        width: exactWidth + 'px',
        height: exactHeight + 'px',
        margin: '0'
      },
      bgcolor: '#ffffff'
    })

    const link = document.createElement('a')
    link.download = `${props.title.replace(/[^\w\s-]/g, '')}_高清排版.png`
    link.href = dataUrl
    link.click()
  } catch (error) {
    console.error('图片生成错误:', error)
  } finally {
    // 恢复预览
    card.style.transform = originalTransform
    wrapper.style.height = originalHeight
    isDownloading.value = false
  }
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@700;900&display=swap');

.card-wrapper {
  width: 100%;
  background-color: #f0f2f6;
  padding: 20px;
}

.control-panel {
  text-align: center;
  margin-bottom: 20px;
}

#preview-wrapper {
  width: 100%;
  overflow: hidden; 
  margin: 0 auto;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
  border-radius: 8px;
  background: #fff;
}

#card-container {
  width: 1600px;
  height: auto;
  background: #ffffff;
  transform-origin: top left;
  display: flex;
  flex-direction: column;
}

.card-header {
  background: #0f172a;
  color: white;
  padding: 60px 80px;
  text-align: center;
  border-bottom: 8px solid #38bdf8;
}

.card-tag {
  font-size: 16px;
  letter-spacing: 3px;
  color: #38bdf8;
  margin-bottom: 20px;
  display: inline-block;
  border: 1px solid rgba(56, 189, 248, 0.4);
  padding: 6px 16px;
  border-radius: 4px;
}

.card-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 56px;
  font-weight: 900;
  line-height: 1.35;
  margin: 0 auto;
  color: #f8fafc;
  max-width: 1300px;
}

.card-body {
  padding: 60px 80px;
  column-count: 3;
  column-gap: 60px;
  column-rule: 1px solid #e2e8f0;
  color: #334155;
  font-size: 22px;
  line-height: 1.8;
  text-align: justify;
}

.card-body :deep(h1), .card-body :deep(h2), .card-body :deep(h3) {
  color: #0f172a;
  font-size: 28px;
  margin-top: 0;
  margin-bottom: 20px;
  border-left: 6px solid #38bdf8;
  padding-left: 15px;
  break-after: avoid;
}

.card-body :deep(p) {
  margin-bottom: 25px;
}

.card-body :deep(blockquote) {
  margin: 0 0 25px 0;
  padding: 20px 25px;
  background: #f8fafc;
  border-left: 4px solid #94a3b8;
  color: #64748b;
  font-style: italic;
  font-size: 20px;
  break-inside: avoid;
}

.card-footer {
  background: #f1f5f9;
  padding: 30px 60px;
  text-align: center;
  font-size: 16px;
  color: #94a3b8;
  border-top: 1px solid #e2e8f0;
  letter-spacing: 2px;
}
</style>
