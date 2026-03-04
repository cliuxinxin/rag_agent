<template>
  <div class="kb-container">
    <el-container>
      <!-- 侧边栏：知识库列表 -->
      <el-aside width="300px">
        <div class="sidebar-header">
          <h2>📚 知识库管理</h2>
          <el-button type="primary" @click="showCreateDialog" :icon="Plus">
            新建知识库
          </el-button>
        </div>

        <div class="kb-list">
          <el-menu
            :default-active="currentKbId"
            @select="selectKb"
          >
            <el-menu-item
              v-for="kb in kbList"
              :key="kb.id"
              :index="kb.id.toString()"
            >
              <el-icon><Folder /></el-icon>
              <span>{{ kb.name }}</span>
              <template #append>
                <el-dropdown trigger="click" @command="handleKbCommand">
                  <el-icon class="more-actions"><MoreFilled /></el-icon>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item :command="{ action: 'delete', kb }">
                        <el-icon><Delete /></el-icon> 删除
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-menu-item>
          </el-menu>
        </div>
      </el-aside>

      <!-- 主内容区：文档管理 -->
      <el-main>
        <div v-if="!currentKbId" class="empty-state">
          <el-empty description="请选择或创建一个知识库" />
        </div>

        <div v-else class="documents-section">
          <div class="section-header">
            <h3>📄 文档管理 - {{ currentKbName }}</h3>
            <el-button type="primary" @click="uploadDocument" :icon="Upload">
              上传文档
            </el-button>
          </div>

          <!-- 健康度检查与 Chunk 搜索 -->
          <div class="health-and-search">
            <el-card class="health-card" v-loading="healthLoading">
              <template #header>
                <div class="card-header">
                  <span>📊 向量索引健康度</span>
                  <el-button 
                    v-if="currentKbHealth?.health_status === 'mismatch' || currentKbHealth?.health_status === 'corrupted'" 
                    type="warning" 
                    size="small" 
                    :loading="resuming"
                    @click="handleResume"
                  >
                    修复索引 / 断点续传
                  </el-button>
                </div>
              </template>
              <div v-if="currentKbHealth">
                <p>
                  <strong>状态：</strong>
                  <el-tag
                    :type="currentKbHealth.health_status === 'healthy'
                      ? 'success'
                      : currentKbHealth.health_status === 'empty'
                        ? 'info'
                        : 'danger'"
                  >
                    {{ currentKbHealth.health_status }}
                  </el-tag>
                </p>
                <p>
                  <strong>JSON 片段数：</strong>{{ currentKbHealth.doc_count }}
                </p>
                <p>
                  <strong>FAISS 向量数：</strong>{{ currentKbHealth.vector_count }}
                </p>
              </div>
              <div v-else>
                <el-empty description="暂无健康度信息" :image-size="80" />
              </div>
            </el-card>

            <el-card class="search-card">
              <template #header>
                <div class="card-header">
                  <span>🔍 片段搜索 (调试向量库)</span>
                </div>
              </template>
              <div class="chunk-search-bar">
                <el-input
                  v-model="chunkSearchKeyword"
                  placeholder="输入关键字，在知识库片段中搜索..."
                  @keyup.enter="searchChunks"
                />
                <el-button
                  type="primary"
                  @click="searchChunks"
                  :loading="chunkSearchLoading"
                >
                  搜索
                </el-button>
              </div>
              <div class="chunk-results" v-loading="chunkSearchLoading">
                <div
                  v-if="chunkSearchResults.length === 0 && !chunkSearchLoading"
                  class="no-results"
                >
                  <span>暂无搜索结果</span>
                </div>
                <el-scrollbar v-else height="200px">
                  <div
                    v-for="(item, idx) in chunkSearchResults"
                    :key="idx"
                    class="chunk-item"
                  >
                    <div class="chunk-meta">
                      <el-tag size="small">
                        {{ item.metadata?.source || 'unknown' }}
                      </el-tag>
                      <span class="chunk-index">#{{ item.id }}</span>
                      <el-button 
                        link 
                        type="primary" 
                        size="small" 
                        @click="toggleVector(item)"
                      >
                        {{ item.showVector ? '隐藏向量' : '查看向量' }}
                      </el-button>
                    </div>
                    <div class="chunk-content">
                      {{ item.content }}
                    </div>
                    <div v-if="item.showVector" class="vector-display">
                      <div v-if="item.vectorLoading" class="vector-loading">Loading...</div>
                      <div v-else class="vector-values">
                        <small>维度: {{ item.vectorData?.dimension }}</small>
                        <div class="vector-array">
                          [{{ item.vectorData?.vector.slice(0, 10).join(', ') }} ... ]
                        </div>
                      </div>
                    </div>
                  </div>
                </el-scrollbar>
              </div>
            </el-card>
          </div>

          <el-table :data="documentList" style="width: 100%" v-loading="loading">
            <el-table-column prop="name" label="文档名称" />
            <el-table-column prop="size" label="大小" width="120" />
            <el-table-column prop="upload_date" label="上传日期" width="180" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="scope">
                <el-button
                  size="small"
                  @click="viewDocument(scope.row)"
                  :icon="View"
                >
                  查看
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="deleteDocument(scope.row)"
                  :icon="Delete"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="totalDocuments"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
            />
          </div>
        </div>
      </el-main>
    </el-container>

    <!-- 新建知识库对话框 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建知识库"
      width="500px"
    >
      <el-form :model="newKbForm" label-width="100px">
        <el-form-item label="知识库名称" required>
          <el-input v-model="newKbForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述" required>
          <el-input
            v-model="newKbForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识库描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createKb" :loading="creating">确定</el-button>
      </template>
    </el-dialog>

    <!-- 上传文档对话框 -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="添加文档"
      width="600px"
    >
      <el-tabs v-model="uploadTab" class="upload-tabs">
        <el-tab-pane label="📁 文件上传" name="file">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :on-change="handleDocumentChange"
            multiple
            accept=".pdf,.txt,.doc,.docx"
            class="upload-area"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 pdf, txt, doc, docx 格式
              </div>
            </template>
          </el-upload>
        </el-tab-pane>
        
        <el-tab-pane label="✍️ 文本粘贴" name="text">
          <el-form label-position="top">
            <el-form-item label="文档名称">
              <el-input v-model="pastedDocName" placeholder="例如：某项目会议纪要" />
            </el-form-item>
            <el-form-item label="文本内容">
              <el-input
                v-model="pastedText"
                type="textarea"
                :rows="10"
                placeholder="在此粘贴长文本内容..."
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div style="margin-top: 20px;">
        <el-radio-group v-model="uploadMode">
          <el-radio label="append">追加到现有库</el-radio>
          <el-radio label="new">重建库 (清空旧数据)</el-radio>
        </el-radio-group>
      </div>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="uploading">确定添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Folder, MoreFilled, Delete, Upload, View, UploadFilled
} from '@element-plus/icons-vue'
import apiClient from '@/api'

const kbList = ref<any[]>([])
const currentKbId = ref<string | null>(null)
const currentKbName = ref('')
const documentList = ref<any[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const totalDocuments = ref(0)
const loading = ref(false)

// 健康度与调试相关状态
const currentKbHealth = ref<any | null>(null)
const healthLoading = ref(false)
const resuming = ref(false)
const chunkSearchKeyword = ref('')
const chunkSearchLoading = ref(false)
const chunkSearchResults = ref<any[]>([])

const createDialogVisible = ref(false)
const creating = ref(false)
const newKbForm = ref({
  name: '',
  description: ''
})

const uploadDialogVisible = ref(false)
const uploading = ref(false)
const selectedDocuments = ref<File[]>([])
const uploadRef = ref()
const uploadTab = ref('file')
const pastedText = ref('')
const pastedDocName = ref('')
const uploadMode = ref('append')

// 加载知识库列表
const loadKbList = async () => {
  try {
    const response: any = await apiClient.get('/api/kb/list')
    const names: string[] = response.kbs || []
    kbList.value = names.map((name, index) => ({
      id: (index + 1).toString(),
      name,
      description: ''
    }))
  } catch (error) {
    console.error('加载知识库失败:', error)
    ElMessage.error('加载知识库失败')
  }
}

// 选择知识库
const selectKb = (kbId: string) => {
  currentKbId.value = kbId
  const kb = kbList.value.find(k => k.id === currentKbId.value)
  currentKbName.value = kb?.name || ''
  loadDocuments()
  loadKbHealth()
}

// 加载文档列表
const loadDocuments = async () => {
  if (!currentKbId.value) return

  loading.value = true
  try {
    const kb = kbList.value.find(k => k.id === currentKbId.value)
    if (!kb) {
      documentList.value = []
      totalDocuments.value = 0
      loading.value = false
      return
    }

    const resp: any = await apiClient.get(`/api/kb/${encodeURIComponent(kb.name)}/documents`)
    const docs = resp.documents || []

    totalDocuments.value = docs.length
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    documentList.value = docs.slice(start, end).map((d: any, idx: number) => ({
      id: idx,
      name: d.name,
      size: `${Math.round((d.total_chars || 0) / 1024)} KB`,
      upload_date: '-'
    }))
  } catch (error) {
    console.error('加载文档失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载健康度
const loadKbHealth = async () => {
  if (!currentKbName.value) return
  healthLoading.value = true
  try {
    const resp = await apiClient.get(`/api/kb/${encodeURIComponent(currentKbName.value)}/health`)
    currentKbHealth.value = resp
  } catch (error) {
    console.error('加载健康度失败:', error)
  } finally {
    healthLoading.value = false
  }
}

const handleResume = async () => {
  resuming.value = true
  try {
    await apiClient.post(`/api/kb/${encodeURIComponent(currentKbName.value)}/resume`)
    ElMessage.success('修复任务已提交/完成')
    loadKbHealth()
  } catch (error) {
    ElMessage.error('修复失败')
  } finally {
    resuming.value = false
  }
}

// 片段搜索
const searchChunks = async () => {
  if (!chunkSearchKeyword.value.trim()) return ElMessage.warning('请输入关键词')
  if (!currentKbName.value) return
  
  chunkSearchLoading.value = true
  try {
    const resp: any = await apiClient.get(`/api/kb/${encodeURIComponent(currentKbName.value)}/chunks/search`, {
      params: { q: chunkSearchKeyword.value, limit: 20 }
    })
    chunkSearchResults.value = (resp.results || []).map((r: any) => ({
      ...r,
      showVector: false,
      vectorLoading: false,
      vectorData: null
    }))
  } catch (error) {
    ElMessage.error('搜索失败')
  } finally {
    chunkSearchLoading.value = false
  }
}

const toggleVector = async (item: any) => {
  item.showVector = !item.showVector
  if (item.showVector && !item.vectorData) {
    item.vectorLoading = true
    try {
      const resp = await apiClient.get(`/api/kb/${encodeURIComponent(currentKbName.value)}/chunks/${item.id}/vector`)
      item.vectorData = resp
    } catch (error) {
      ElMessage.error('读取向量失败')
    } finally {
      item.vectorLoading = false
    }
  }
}

// 其他方法保持原有逻辑，增加必要的类型转换和空判断...
const showCreateDialog = () => {
  newKbForm.value = { name: '', description: '' }
  createDialogVisible.value = true
}

const createKb = async () => {
  if (!newKbForm.value.name) return ElMessage.warning('请输入名称')
  creating.value = true
  try {
    // 模拟创建
    await new Promise(resolve => setTimeout(resolve, 500))
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    loadKbList()
  } finally {
    creating.value = false
  }
}

const handleKbCommand = (command: any) => {
  if (command.action === 'delete') {
    ElMessageBox.confirm(`确定删除 ${command.kb.name} 吗？`, '警告', { type: 'warning' }).then(async () => {
      await apiClient.delete(`/api/kb/${encodeURIComponent(command.kb.name)}`)
      ElMessage.success('删除成功')
      loadKbList()
      if (currentKbName.value === command.kb.name) {
        currentKbId.value = null
        currentKbName.value = ''
      }
    })
  }
}

const uploadDocument = () => {
  selectedDocuments.value = []
  uploadRef.value?.clearFiles()
  uploadDialogVisible.value = true
}

const handleDocumentChange = (file: any) => {
  if (file.raw) selectedDocuments.value.push(file.raw)
}

const confirmUpload = async () => {
  if (uploadTab.value === 'file' && selectedDocuments.value.length === 0) return ElMessage.warning('请选择文件')
  if (uploadTab.value === 'text' && !pastedText.value.trim()) return ElMessage.warning('请输入文本')
  
  uploading.value = true
  try {
    if (uploadTab.value === 'file') {
      const formData = new FormData()
      formData.append('kb_name', currentKbName.value)
      formData.append('mode', uploadMode.value)
      selectedDocuments.value.forEach(f => formData.append('files', f))
      await apiClient.post('/api/kb/upload', formData)
    } else {
      const formData = new FormData()
      formData.append('kb_name', currentKbName.value)
      formData.append('text', pastedText.value)
      formData.append('doc_name', pastedDocName.value || '未命名文本')
      formData.append('mode', uploadMode.value)
      await apiClient.post('/api/kb/add_text', formData)
    }
    
    ElMessage.success('添加成功')
    uploadDialogVisible.value = false
    loadDocuments()
    loadKbHealth()
    
    // 重置表单
    pastedText.value = ''
    pastedDocName.value = ''
    selectedDocuments.value = []
    uploadRef.value?.clearFiles()
  } catch (error: any) {
    ElMessage.error(`添加失败: ${error.message || '未知错误'}`)
  } finally {
    uploading.value = false
  }
}

const viewDocument = (doc: any) => ElMessage.info('开发中...')

const deleteDocument = (doc: any) => {
  ElMessageBox.confirm(`确定删除 ${doc.name} 吗？`, '警告', { type: 'warning' }).then(() => {
    ElMessage.success('已模拟删除')
  })
}

onMounted(loadKbList)
</script>

<style scoped>
.kb-container {
  height: 100vh;
  background: #f5f7fa;
}

.el-container {
  height: 100%;
}

.el-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.kb-list {
  flex: 1;
  overflow-y: auto;
}

.more-actions {
  cursor: pointer;
  color: #909399;
}

.el-main {
  background: #fff;
  padding: 0;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.documents-section {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.health-and-search {
  display: flex;
  gap: 16px;
  padding: 16px 20px 0;
}

.health-card,
.search-card {
  flex: 1;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chunk-search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.chunk-item {
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chunk-index {
  font-size: 12px;
  color: #909399;
}

.chunk-content {
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
  white-space: pre-wrap;
}

.vector-display {
  margin-top: 8px;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
}

.vector-array {
  font-family: monospace;
  font-size: 11px;
  color: #67c23a;
  word-break: break-all;
}

.section-header {
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  padding: 20px;
  border-top: 1px solid #e4e7ed;
}
</style>
