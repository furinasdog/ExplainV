<template>
  <div>
    <div class="page-header">
      <div>
        <h2>我的任务</h2>
      </div>
      <router-link to="/create">
        <button class="btn btn-primary">新建任务</button>
      </router-link>
    </div>

    <div v-if="loading" class="blankslate">加载中...</div>
    <div v-else-if="tasks.length === 0" class="blankslate card">
      <p>暂无任务</p>
      <router-link to="/create">创建你的第一个任务 →</router-link>
    </div>

    <div v-else class="task-list">
      <TaskCard v-for="task in tasks" :key="task.id" :task="task" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import api from '../api/index.js';
import TaskCard from '../components/TaskCard.vue';

const tasks = ref([]);
const loading = ref(true);
let timer = null;

async function fetchTasks() {
  try {
    const { data } = await api.get('/api/tasks');
    tasks.value = data;
  } catch { /* */ }
  loading.value = false;
}

onMounted(() => {
  fetchTasks();
  timer = setInterval(fetchTasks, 30_000);
});

onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}
h2 {
  font-size: 24px;
  font-weight: 600;
}
.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.blankslate {
  text-align: center;
  padding: 48px 16px;
  color: var(--color-text-secondary);
}
.blankslate p {
  font-size: 16px;
  margin-bottom: 8px;
}
</style>
