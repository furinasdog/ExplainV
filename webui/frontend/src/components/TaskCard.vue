<template>
  <div class="task-card card">
    <div class="card-body">
      <div class="card-header">
        <div class="task-meta">
          <span class="task-id mono">#{{ task.id.slice(0, 8) }}</span>
          <span class="badge" :class="'badge-' + task.status">{{ statusLabel }}</span>
        </div>
        <span class="time">{{ formatTime(task.createdAt) }}</span>
      </div>

      <!-- Progress -->
      <div v-if="task.status === 'running' || task.status === 'starting'" class="progress-section">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${(task.progress || 0) * 100}%` }"></div>
        </div>
        <div class="progress-info">
          <span class="stage">{{ stageLabel }}</span>
          <span class="pct">{{ ((task.progress || 0) * 100).toFixed(0) }}%</span>
        </div>
      </div>

      <!-- Queued -->
      <div v-if="task.status === 'queued'" class="queued-info">
        <span>🕐 任务排队中，等待空闲资源...</span>
      </div>

      <!-- Error -->
      <div v-if="task.error" class="error-box">
        {{ task.error }}
      </div>

      <!-- Result -->
      <div v-if="task.status === 'completed'" class="result-section">
        <a v-if="task.videoUrl" :href="task.videoUrl" target="_blank" class="btn btn-sm btn-primary">
          ⬇ 下载视频
        </a>
        <details v-if="task.explanation" class="explanation">
          <summary>查看讲解内容</summary>
          <pre class="explanation-text">{{ task.explanation }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({ task: { type: Object, required: true } });

const stageMap = {
  scaling_up: '启动集群中',
  submitted: '已提交',
  initializing: '初始化中',
  explanation: '生成讲解中',
  code_generation: '生成代码中',
  code_reviewing: '审查代码中',
  rendering: '渲染视频中',
  code_fixing: '自动修复代码中',
  done: '已完成',
  queued: '排队中',
};

const statusMap = {
  starting: '启动中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  queued: '排队中',
};

const statusLabel = computed(() => statusMap[props.task.status] || props.task.status);
const stageLabel = computed(() => stageMap[props.task.stage] || props.task.stage || '');

function formatTime(iso) {
  try { return new Date(iso).toLocaleString('zh-CN'); } catch { return iso; }
}
</script>

<style scoped>
.task-card {
  padding: 16px;
  transition: border-color 0.15s;
}
.task-card:hover {
  border-color: var(--color-text-tertiary);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-id {
  color: var(--color-text-tertiary);
}
.time {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
.progress-section {
  margin: 12px 0;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.queued-info {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--color-attention-subtle, rgba(210, 153, 34, 0.1));
  color: var(--color-attention, #9a6700);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.error-box {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--color-danger-subtle);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: 13px;
  border: 1px solid rgba(207, 34, 46, 0.15);
}
.result-section {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-section .btn {
  align-self: flex-start;
}
details {
  font-size: 13px;
}
summary {
  cursor: pointer;
  color: var(--color-text-link);
  font-weight: 500;
}
.explanation-text {
  margin-top: 8px;
  white-space: pre-wrap;
  font-size: 13px;
  font-family: var(--font-mono);
  background: var(--color-bg-inset);
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-muted);
  max-height: 300px;
  overflow-y: auto;
  color: var(--color-text);
}
</style>
