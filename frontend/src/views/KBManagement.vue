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
      title="上传文档"
      width="600px"
    >
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
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="uploading">上传</el-button>
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

const kbList = ref<any[]>([])
const currentKbId = ref<number | null>(null)
const currentKbName = ref('')
const documentList = ref<any[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const totalDocuments = ref(0)
const loading = ref(false)

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

// 加载知识库列表
const loadKbList = async () => {
  try {
    // TODO: 调用实际 API
    // const response = await apiClient.get('/api/kb/list')
    // kbList.value = response.kbs
    
    // 模拟数据
    kbList.value = [
      { id: 1, name: '技术文档', description: '技术相关文档' },
      { id: 2, name: '产品手册', description: '产品使用手册' }
    ]
  } catch (error) {
    console.error('加载知识库失败:', error)
  }
}

// 选择知识库
const selectKb = (kbId: string) => {
  currentKbId.value = parseInt(kbId)
  const kb = kbList.value.find(k => k.id === currentKbId.value)
  currentKbName.value = kb?.name || ''
  loadDocuments()
}

// 加载文档列表
const loadDocuments = async () => {
  if (!currentKbId.value) return
  
  loading.value = true
  try {
    // TODO: 调用实际 API
    // const response = await apiClient.get(`/api/kb/${currentKbId.value}/documents`, {
    //   params: { page: currentPage.value, size: pageSize.value }
    // })
    
    // 模拟数据
    setTimeout(() => {
      documentList.value = [
        { id: 1, name: '文档 1.pdf', size: '1.2 MB', upload_date: '2024-01-01' },
        { id: 2, name: '文档 2.txt', size: '256 KB', upload_date: '2024-01-02' }
      ]
      totalDocuments.value = 2
      loading.value = false
    }, 500)
  } catch (error) {
    console.error('加载文档失败:', error)
    loading.value = false
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  newKbForm.value = { name: '', description: '' }
  createDialogVisible.value = true
}

// 创建知识库
const createKb = async () => {
  if (!newKbForm.value.name) {
    ElMessage.warning('请输入知识库名称')
    return
  }

  creating.value = true
  try {
    // TODO: 调用实际 API
    // await apiClient.post('/api/kb/create', newKbForm.value)
    
    await new Promise(resolve => setTimeout(resolve, 500))
    
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    loadKbList()
  } catch (error) {
    console.error('创建失败:', error)
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

// 处理知识库操作
const handleKbCommand = (command: any) => {
  if (command.action === 'delete') {
    ElMessageBox.confirm(
      `确定要删除知识库 "${command.kb.name}" 吗？`,
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    ).then(async () => {
      try {
        // TODO: 调用实际 API
        // await apiClient.delete(`/api/kb/delete/${command.kb.id}`)
        
        ElMessage.success('删除成功')
        loadKbList()
        if (currentKbId.value === command.kb.id) {
          currentKbId.value = null
          documentList.value = []
        }
      } catch (error) {
        console.error('删除失败:', error)
        ElMessage.error('删除失败')
      }
    }).catch(() => {})
  }
}

// 上传文档
const uploadDocument = () => {
  selectedDocuments.value = []
  uploadRef.value?.clearFiles()
  uploadDialogVisible.value = true
}

const handleDocumentChange = (file: any) => {
  if (file.raw) {
    selectedDocuments.value.push(file.raw)
  }
}

const confirmUpload = async () => {
  if (selectedDocuments.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    // TODO: 调用实际 API 上传
    // const formData = new FormData()
    // selectedDocuments.value.forEach(file => {
    //   formData.append('files', file)
    // })
    // await apiClient.post(`/api/kb/${currentKbId.value}/upload`, formData)
    
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    loadDocuments()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

// 查看文档
const viewDocument = (doc: any) => {
  ElMessage.info('查看功能开发中...')
}

// 删除文档
const deleteDocument = async (doc: any) => {
  ElMessageBox.confirm(
    `确定要删除文档 "${doc.name}" 吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      // TODO: 调用实际 API
      // await apiClient.delete(`/api/kb/document/${doc.id}`)
      
      ElMessage.success('删除成功')
      loadDocuments()
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(() => {
  loadKbList()
})
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
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.sidebar-header h2 {
  margin-bottom: 15px;
  font-size: 18px;
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
  background: #fff;
}

.upload-area {
  width: 100%;
}
</style>
