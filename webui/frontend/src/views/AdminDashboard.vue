<template>
  <div>
    <div class="page-header">
      <h2>管理面板</h2>
    </div>

    <div class="tab-nav">
      <button :class="['tab-btn', { active: tab === 'pods' }]" @click="tab = 'pods'">Pod 管理</button>
      <button :class="['tab-btn', { active: tab === 'users' }]" @click="tab = 'users'">用户管理</button>
      <button :class="['tab-btn', { active: tab === 'tasks' }]" @click="tab = 'tasks'">全部任务</button>
    </div>

    <!-- Pods -->
    <div v-if="tab === 'pods'" class="tab-content">
      <div class="section-header">
        <h3>运行中的 Pod ({{ pods.length }})</h3>
        <div class="actions">
          <input v-model.number="scaleTarget" type="number" min="0" max="20" class="input scale-input" />
          <button class="btn btn-sm" @click="handleScale">扩缩容</button>
          <button class="btn btn-sm" @click="fetchPods">刷新</button>
        </div>
      </div>

      <div v-if="loadingPods" class="blankslate">加载中...</div>
      <div v-else-if="pods.length === 0" class="blankslate card">暂无运行中的 Pod</div>
      <table v-else class="data-table">
        <thead><tr><th>Pod 名称</th><th>状态</th><th>就绪</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="pod in pods" :key="pod.name">
            <td class="mono">{{ pod.name }}</td>
            <td><span class="badge" :class="'badge-' + pod.status.toLowerCase()">{{ pod.status }}</span></td>
            <td>{{ pod.ready ? '✅' : '⏳' }}</td>
            <td>{{ formatTime(pod.createdAt) }}</td>
            <td class="action-cell">
              <button class="btn btn-sm btn-secondary" @click="handleViewLogs(pod.name)" :disabled="!pod.ready">📋 日志</button>
              <button class="btn btn-sm btn-danger" @click="handleDeletePod(pod.name)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Users -->
    <div v-if="tab === 'users'" class="tab-content">
      <div class="section-header">
        <h3>用户列表 ({{ users.length }})</h3>
        <button class="btn btn-sm btn-primary" @click="showCreateUser = !showCreateUser">新建用户</button>
      </div>

      <div v-if="showCreateUser" class="create-form card">
        <input class="input" v-model="newUser.username" placeholder="用户名" />
        <input class="input" v-model="newUser.password" type="password" placeholder="密码" />
        <select v-model="newUser.role">
          <option value="user">普通用户</option>
          <option value="admin">管理员</option>
        </select>
        <div class="create-actions">
          <button class="btn btn-sm btn-primary" @click="handleCreateUser">创建</button>
          <button class="btn btn-sm" @click="showCreateUser = false">取消</button>
        </div>
        <p v-if="userError" class="flash-error">{{ userError }}</p>
      </div>

      <table class="data-table">
        <thead><tr><th>用户名</th><th>角色</th><th>注册时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.username">
            <td>{{ u.username }}</td>
            <td><span class="badge" :class="u.role === 'admin' ? 'badge-admin' : 'badge-cancelled'">{{ u.role === 'admin' ? '管理员' : '用户' }}</span></td>
            <td>{{ formatTime(u.createdAt) }}</td>
            <td>
              <button v-if="u.username !== userStore.username" class="btn btn-sm btn-danger" @click="handleDeleteUser(u.username)">删除</button>
              <span v-else class="hint-text">(当前)</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- All Tasks -->
    <div v-if="tab === 'tasks'" class="tab-content">
      <div class="section-header">
        <h3>全部任务 ({{ allTasks.length }})</h3>
        <button class="btn btn-sm btn-danger" @click="handleCleanup">🧹 清理卡住的任务</button>
      </div>

      <div v-if="allTasks.length === 0" class="blankslate card">暂无任务</div>
      <table v-else class="data-table">
        <thead><tr><th>ID</th><th>用户</th><th>状态</th><th>进度</th><th>创建时间</th></tr></thead>
        <tbody>
          <tr v-for="t in allTasks" :key="t.id">
            <td class="mono">#{{ t.id.slice(0, 8) }}</td>
            <td>{{ t.username }}</td>
            <td><span class="badge" :class="'badge-' + t.status">{{ t.status }}</span></td>
            <td>{{ ((t.progress || 0) * 100).toFixed(0) }}%</td>
            <td>{{ formatTime(t.createdAt) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pod Logs Modal -->
    <div v-if="showLogsModal" class="modal-overlay" @click.self="showLogsModal = false">
      <div class="modal-content card">
        <div class="modal-header">
          <h3>📋 Pod 日志 — {{ logPodName }}</h3>
          <div class="modal-actions">
            <button class="btn btn-sm" @click="handleRefreshLogs" :disabled="loadingLogs">刷新</button>
            <button class="btn btn-sm" @click="showLogsModal = false">关闭</button>
          </div>
        </div>
        <div class="log-container">
          <div v-if="loadingLogs" class="blankslate">加载日志中...</div>
          <pre v-else-if="podLogs" class="log-text">{{ podLogs }}</pre>
          <div v-else class="blankslate">暂无日志</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useUserStore } from '../stores/user.js';
import api from '../api/index.js';

const userStore = useUserStore();

const tab = ref('pods');
const pods = ref([]);
const users = ref([]);
const allTasks = ref([]);
const loadingPods = ref(false);
const scaleTarget = ref(0);
const showCreateUser = ref(false);
const newUser = ref({ username: '', password: '', role: 'user' });
const userError = ref('');

// Pod logs
const showLogsModal = ref(false);
const logPodName = ref('');
const podLogs = ref('');
const loadingLogs = ref(false);

async function fetchPods() {
  loadingPods.value = true;
  try {
    const { data } = await api.get('/api/admin/pods');
    pods.value = data.pods || [];
    scaleTarget.value = data.desiredReplicas || 0;
  } catch { /* */ }
  loadingPods.value = false;
}

async function fetchUsers() {
  try { const { data } = await api.get('/api/auth/admin/users'); users.value = data; } catch { /* */ }
}

async function fetchAllTasks() {
  try { const { data } = await api.get('/api/admin/tasks'); allTasks.value = data; } catch { /* */ }
}

async function handleDeletePod(name) {
  if (!confirm(`确认强制删除 Pod: ${name}？`)) return;
  try { await api.delete(`/api/admin/pods/${name}`); await fetchPods(); }
  catch (err) { alert(err.response?.data?.error || '删除失败'); }
}

async function handleScale() {
  try { await api.put('/api/admin/pods/scale', { replicas: scaleTarget.value }); await fetchPods(); }
  catch (err) { alert(err.response?.data?.error || '扩缩容失败'); }
}

async function handleCreateUser() {
  userError.value = '';
  try {
    await api.post('/api/auth/admin/users', newUser.value);
    showCreateUser.value = false;
    newUser.value = { username: '', password: '', role: 'user' };
    await fetchUsers();
  } catch (err) { userError.value = err.response?.data?.error || '创建失败'; }
}

async function handleDeleteUser(username) {
  if (!confirm(`确认删除用户: ${username}？`)) return;
  try { await api.delete(`/api/auth/admin/users/${username}`); await fetchUsers(); }
  catch (err) { alert(err.response?.data?.error || '删除失败'); }
}

async function handleCleanup() {
  if (!confirm('确认将所有运行中/启动中的任务标记为失败？')) return;
  try {
    const { data } = await api.post('/api/admin/tasks/cleanup');
    alert(data.message);
    await fetchAllTasks();
  } catch (err) { alert(err.response?.data?.error || '清理失败'); }
}

async function handleViewLogs(podName) {
  logPodName.value = podName;
  showLogsModal.value = true;
  loadingLogs.value = true;
  podLogs.value = '';
  try {
    const { data } = await api.get(`/api/admin/pods/${podName}/logs`);
    podLogs.value = data.logs || '暂无日志';
  } catch (err) {
    podLogs.value = `获取日志失败: ${err.response?.data?.error || err.message}`;
  }
  loadingLogs.value = false;
}

async function handleRefreshLogs() {
  if (!logPodName.value) return;
  await handleViewLogs(logPodName.value);
}

function formatTime(iso) {
  try { return new Date(iso).toLocaleString('zh-CN'); } catch { return iso; }
}

onMounted(() => { fetchPods(); fetchUsers(); fetchAllTasks(); });
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}
h2 { font-size: 24px; font-weight: 600; }

.tab-nav {
  display: flex;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 16px;
}
.tab-btn {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  margin-bottom: -1px;
}
.tab-btn:hover { color: var(--color-text); }
.tab-btn.active {
  color: var(--color-text);
  border-bottom-color: #fd8c73;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
h3 { font-size: 16px; font-weight: 600; }
.actions { display: flex; gap: 8px; align-items: center; }
.scale-input { width: 64px; text-align: center; padding: 3px 8px; font-size: 13px; }

.action-cell {
  display: flex;
  gap: 4px;
  align-items: center;
}
.btn-secondary {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}
.btn-secondary:hover {
  background: var(--color-bg-secondary);
}

.create-form {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.create-form .input { width: auto; flex: 1; min-width: 120px; }
.create-form select { width: auto; padding: 5px 8px; font-size: 14px; }
.create-actions { display: flex; gap: 4px; }

.flash-error {
  width: 100%;
  padding: 6px 10px;
  background: var(--color-danger-subtle);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: 13px;
  margin-top: 4px;
}
.hint-text { font-size: 12px; color: var(--color-text-tertiary); }
.blankslate { text-align: center; padding: 32px; color: var(--color-text-secondary); }

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 200;
  padding: 24px;
}
.modal-content {
  width: 100%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding: 20px;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}
.modal-actions {
  display: flex;
  gap: 8px;
}
.log-container {
  flex: 1;
  overflow: auto;
  min-height: 200px;
}
.log-text {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--color-bg-inset, #0d1117);
  color: var(--color-text, #c9d1d9);
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-muted);
  margin: 0;
}
</style>
