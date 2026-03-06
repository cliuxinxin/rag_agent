<template>
  <div class="studio-container">
    <!-- 1. 左侧：素材情报局 -->
    <aside class="assets-panel">
      <div class="panel-header">
        <h3>📦 素材情报局</h3>
        <el-button type="primary" link @click="addAssetDialog = true">+ 添加</el-button>
      </div>
      
      <el-scrollbar class="assets-list">
        <div v-for="(asset, idx) in assets" :key="idx" class="asset-card">
          <div class="asset-type">
            <el-tag size="small">{{ asset.type }}</el-tag>
            <el-button type="text" icon="Delete" class="del-asset" @click="removeAsset(idx)"></el-button>
          </div>
          <div class="asset-preview">{{ asset.content.slice(0, 50) }}...</div>
        </div>
        <el-empty v-if="assets.length === 0" description="暂无素材，请添加" image-size="60" />
      </el-scrollbar>

      <div class="global-config">
        <h4>🛠️ 全局设置</h4>
        <el-form label-position="top" size="small">
          <el-form-item label="核心需求">
            <el-input v-model="config.requirements" type="textarea" :rows="2" placeholder="你想写什么？" />
          </el-form-item>
          <el-form-item label="语调">
            <el-select v-model="config.tone" style="width: 100%">
              <el-option value="深度专业" label="深度专业" />
              <el-option value="幽默风趣" label="幽默风趣" />
              <el-option value="新闻报道" label="新闻报道" />
            </el-select>
          </el-form-item>
          <el-button type="primary" style="width: 100%" @click="genOutline" :loading="isOutlining">
            ✨ 生成/重置大纲
          </el-button>
        </el-form>
      </div>
    </aside>

    <!-- 2. 中间：积木式撰稿台 -->
    <main class="workbench">
      <div v-if="outline.length === 0" class="empty-workbench">
        <el-result icon="info" title="准备就绪" sub-title="请在左侧添加素材并生成大纲" />
      </div>

      <div v-else class="cards-flow">
        <draggable v-model="outline" item-key="id" @end="autoSave">
          <template #item="{ element: section, index }">
            <el-card class="section-card" shadow="hover">
              <!-- 卡片头：章节控制 -->
              <div class="card-header">
                <div class="title-edit">
                  <el-tag type="info" size="small">{{ index + 1 }}</el-tag>
                  <el-input v-model="section.title" class="title-input" placeholder="章节标题" @change="autoSave" />
                </div>
                <div class="card-actions">
                  <el-button 
                    type="primary" 
                    size="small" 
                    :loading="section.status === 'generating'"
                    @click="generateSection(section)"
                  >
                    {{ section.status === 'empty' ? '✍️ 生成' : '🔄 重写' }}
                  </el-button>
                  <el-button type="danger" icon="Delete" circle size="small" @click="removeSection(index)" />
                </div>
              </div>

              <!-- 卡片体：指令与内容 -->
              <div class="card-body">
                <el-input 
                  v-if="section.status === 'empty'"
                  v-model="section.gist" 
                  placeholder="本章核心写作指令（AI 将基于此生成）" 
                  size="small"
                  @change="autoSave"
                />
                
                <div v-else class="editor-area">
                  <el-input
                    v-model="section.content"
                    type="textarea"
                    autosize
                    placeholder="生成的内容将显示在这里..."
                    @change="autoSave"
                  />
                </div>
              </div>
            </el-card>
          </template>
        </draggable>
        
        <!-- 底部添加按钮 -->
        <div class="add-section-btn" @click="addEmptySection">
          <el-icon><Plus /></el-icon> 添加新章节
        </div>
      </div>
    </main>

    <!-- 3. 右侧：预览与导出 -->
    <aside class="preview-panel">
      <div class="panel-header">
        <h3>📄 全文预览</h3>
        <el-button type="success" size="small" @click="exportMarkdown">导出 MD</el-button>
      </div>
      <div class="markdown-preview markdown-body" v-html="fullHtml"></div>
    </aside>

    <!-- 添加素材弹窗 -->
    <el-dialog v-model="addAssetDialog" title="添加素材" width="500px">
      <el-tabs v-model="assetTab">
        <el-tab-pane label="文本" name="text">
          <el-input v-model="newAssetContent" type="textarea" :rows="6" placeholder="粘贴文本..." />
        </el-tab-pane>
        <!-- 可以扩展文件上传 -->
      </el-tabs>
      <template #footer>
        <el-button @click="addAssetDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmAddAsset">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import draggable from 'vuedraggable'
import { marked } from 'marked'
import { Plus, Delete } from '@element-plus/icons-vue'
import { createV3Project, updateAssets, generateV3Outline, saveV3Project, SECTION_STREAM_URL } from '../api/writeV3'
import { ElMessage } from 'element-plus'

// State
const projectId = ref('')
const assets = ref<any[]>([])
const outline = ref<any[]>([])
const config = ref({ requirements: '', tone: '深度专业', length: '标准' })

// UI State
const addAssetDialog = ref(false)
const assetTab = ref('text')
const newAssetContent = ref('')
const isOutlining = ref(false)

// Init
onMounted(async () => {
  const res: any = await createV3Project("未命名项目 " + new Date().toLocaleString())
  projectId.value = res.project_id
})

// Methods
const confirmAddAsset = async () => {
  if (!newAssetContent.value) return
  assets.value.push({ type: 'text', content: newAssetContent.value })
  await updateAssets(projectId.value, assets.value)
  newAssetContent.value = ''
  addAssetDialog.value = false
  ElMessage.success('素材已添加')
}

const removeAsset = async (idx: number) => {
  assets.value.splice(idx, 1)
  await updateAssets(projectId.value, assets.value)
}

const genOutline = async () => {
  if (assets.value.length === 0) return ElMessage.warning('请先添加素材')
  isOutlining.value = true
  try {
    const res: any = await generateV3Outline(projectId.value, config.value.requirements, config.value.tone, '标准')
    outline.value = res.outline
  } catch (e) {
    ElMessage.error('生成大纲失败')
  } finally {
    isOutlining.value = false
  }
}

const generateSection = async (section: any) => {
  section.status = 'generating'
  section.content = '' // 清空旧内容
  
  try {
    const response = await fetch(SECTION_STREAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId.value,
        section_id: section.id,
        tone: config.value.tone,
        length: '标准'
      })
    })
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    
    while (true) {
      const { done, value } = await reader!.read()
      if (done) break
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            section.status = 'done'
            autoSave()
          } else {
            try {
              const json = JSON.parse(data)
              if (json.content) section.content += json.content
            } catch (e) {}
          }
        }
      }
    }
  } catch (e) {
    section.status = 'empty'
    ElMessage.error('生成失败')
  }
}

const addEmptySection = () => {
  outline.value.push({
    id: 'temp_' + Date.now(),
    title: '新章节',
    gist: '',
    status: 'empty',
    content: ''
  })
}

const removeSection = (idx: number) => {
  outline.value.splice(idx, 1)
  autoSave()
}

const autoSave = async () => {
  await saveV3Project(projectId.value, outline.value)
}

// Computed Preview
const fullHtml = computed(() => {
  const md = outline.value.map(s => `## ${s.title}\n\n${s.content || '(待生成...)'}`).join('\n\n')
  return marked(md)
})

const exportMarkdown = () => {
  const blob = new Blob([outline.value.map(s => `## ${s.title}\n\n${s.content}`).join('\n\n')], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'article.md'
  a.click()
}
</script>

<style scoped>
.studio-container {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

.assets-panel, .preview-panel {
  width: 300px;
  background: #fff;
  border-right: 1px solid #eee;
  display: flex;
  flex-direction: column;
  padding: 15px;
}

.preview-panel {
  border-left: 1px solid #eee;
  border-right: none;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.assets-list {
  flex: 1;
  margin-bottom: 20px;
}

.asset-card {
  background: #f9f9f9;
  padding: 10px;
  margin-bottom: 10px;
  border-radius: 6px;
  font-size: 12px;
}

.asset-type {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.workbench {
  flex: 1;
  padding: 20px 40px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.cards-flow {
  width: 100%;
  max-width: 800px;
}

.section-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.title-edit {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.title-input {
  font-weight: bold;
}

.add-section-btn {
  text-align: center;
  padding: 15px;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  color: #909399;
}

.add-section-btn:hover {
  border-color: #409eff;
  color: #409eff;
}

.markdown-preview {
  flex: 1;
  overflow-y: auto;
  font-size: 13px;
}
</style>