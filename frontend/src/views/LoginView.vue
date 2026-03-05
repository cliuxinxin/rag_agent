<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>RAG Agent 登录</h2>
        </div>
      </template>
      <el-form :model="loginForm" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="loginForm.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="请输入密码" 
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="isLoading" block>
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <p>默认账号: admin / admin123</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import apiClient from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const isLoading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  isLoading.value = true
  try {
    // 使用 URLSearchParams 模拟表单提交，匹配 OAuth2PasswordRequestForm
    const params = new URLSearchParams()
    params.append('username', loginForm.username)
    params.append('password', loginForm.password)

    const resp: any = await apiClient.post('/api/auth/login', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })

    if (resp.access_token) {
      localStorage.setItem('token', resp.access_token)
      localStorage.setItem('username', loginForm.username)
      ElMessage.success('登录成功')
      
      const redirect = route.query.redirect as string || '/'
      router.push(redirect)
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '登录失败，请检查用户名或密码')
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f7fa;
}

.login-card {
  width: 400px;
}

.card-header {
  text-align: center;
}

.card-header h2 {
  margin: 0;
  font-weight: 600;
  color: #409eff;
}

.login-footer {
  margin-top: 20px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

:deep(.el-button--primary) {
  width: 100%;
}
</style>
