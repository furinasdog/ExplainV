<template>
  <div>
    <div class="page-header">
      <h2>Admin</h2>
    </div>

    <div class="tab-nav">
      <button :class="['tab-btn', { active: tab === 'pods' }]" @click="tab = 'pods'">Pods</button>
      <button :class="['tab-btn', { active: tab === 'users' }]" @click="tab = 'users'">Users</button>
      <button :class="['tab-btn', { active: tab === 'tasks' }]" @click="tab = 'tasks'">All tasks</button>
    </div>

    <!-- Pods -->
    <div v-if="tab === 'pods'" class="tab-content">
      <div class="section-header">
        <h3>Running Pods ({{ pods.length }})</h3>
        <div class="actions">
          <input v-model.number="scaleTarget" type="number" min="0" max="10" class="input scale-input" />
          <button class="btn btn-sm" @click="handleScale">Scale</button>
          <button class="btn btn-sm" @click="fetchPods">Refresh</button>
        </div>
      </div>

      <div v-if="loadingPods" class="blankslate">Loading...</div>
      <div v-else-if="pods.length === 0" class="blankslate card">No running Pods</div>
      <table v-else class="data-table">
        <thead><tr><th>Pod Name</th><th>Status</th><th>Ready</th><th>Created</th><th></th></tr></thead>
        <tbody>
          <tr v-for="pod in pods" :key="pod.name">
            <td class="mono">{{ pod.name }}</td>
            <td><span class="badge" :class="'badge-' + pod.status.toLowerCase()">{{ pod.status }}</span></td>
            <td>{{ pod.ready ? '✅' : '⏳' }}</td>
            <td>{{ formatTime(pod.createdAt) }}</td>
            <td><button class="btn btn-sm btn-danger" @click="handleDeletePod(pod.name)">Delete</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Users -->
    <div v-if="tab === 'users'" class="tab-content">
      <div class="section-header">
        <h3>Users ({{ users.length }})</h3>
        <button class="btn btn-sm btn-primary" @click="showCreateUser = !showCreateUser">New user</button>
      </div>

      <div v-if="showCreateUser" class="create-form card">
        <input class="input" v-model="newUser.username" placeholder="Username" />
        <input class="input" v-model="newUser.password" type="password" placeholder="Password" />
        <select v-model="newUser.role">
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </select>
        <div class="create-actions">
          <button class="btn btn-sm btn-primary" @click="handleCreateUser">Create</button>
          <button class="btn btn-sm" @click="showCreateUser = false">Cancel</button>
        </div>
        <p v-if="userError" class="flash-error">{{ userError }}</p>
      </div>

      <table class="data-table">
        <thead><tr><th>Username</th><th>Role</th><th>Registered</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.username">
            <td>{{ u.username }}</td>
            <td><span class="badge" :class="u.role === 'admin' ? 'badge-admin' : 'badge-cancelled'">{{ u.role === 'admin' ? 'Admin' : 'User' }}</span></td>
            <td>{{ formatTime(u.createdAt) }}</td>
            <td>
              <button v-if="u.username !== userStore.username" class="btn btn-sm btn-danger" @click="handleDeleteUser(u.username)">Delete</button>
              <span v-else class="hint-text">(you)</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- All Tasks -->
    <div v-if="tab === 'tasks'" class="tab-content">
      <div class="section-header">
        <h3>All tasks ({{ allTasks.length }})</h3>
        <button class="btn btn-sm btn-danger" @click="handleCleanup">🧹 Cleanup stuck tasks</button>
      </div>

      <div v-if="allTasks.length === 0" class="blankslate card">No tasks</div>
      <table v-else class="data-table">
        <thead><tr><th>ID</th><th>User</th><th>Status</th><th>Progress</th><th>Created</th></tr></thead>
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
  if (!confirm(`Force delete Pod: ${name}?`)) return;
  try { await api.delete(`/api/admin/pods/${name}`); await fetchPods(); }
  catch (err) { alert(err.response?.data?.error || 'Delete failed'); }
}

async function handleScale() {
  try { await api.put('/api/admin/pods/scale', { replicas: scaleTarget.value }); await fetchPods(); }
  catch (err) { alert(err.response?.data?.error || 'Scale failed'); }
}

async function handleCreateUser() {
  userError.value = '';
  try {
    await api.post('/api/auth/admin/users', newUser.value);
    showCreateUser.value = false;
    newUser.value = { username: '', password: '', role: 'user' };
    await fetchUsers();
  } catch (err) { userError.value = err.response?.data?.error || 'Create failed'; }
}

async function handleDeleteUser(username) {
  if (!confirm(`Delete user: ${username}?`)) return;
  try { await api.delete(`/api/auth/admin/users/${username}`); await fetchUsers(); }
  catch (err) { alert(err.response?.data?.error || 'Delete failed'); }
}

async function handleCleanup() {
  if (!confirm('Mark all running/starting tasks as failed?')) return;
  try {
    const { data } = await api.post('/api/admin/tasks/cleanup');
    alert(data.message);
    await fetchAllTasks();
  } catch (err) { alert(err.response?.data?.error || 'Cleanup failed'); }
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
</style>