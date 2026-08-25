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

      <!-- Error -->
      <div v-if="task.error" class="error-box">
        {{ task.error }}
      </div>

      <!-- Result -->
      <div v-if="task.status === 'completed'" class="result-section">
        <a v-if="task.videoUrl" :href="task.videoUrl" target="_blank" class="btn btn-sm btn-primary">
          ⬇ Download video
        </a>
        <details v-if="task.explanation" class="explanation">
          <summary>View explanation</summary>
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
  scaling_up: 'Starting cluster',
  submitted: 'Submitted',
  initializing: 'Initializing',
  explanation: 'Generating explanation',
  code_generation: 'Generating code',
  code_reviewing: 'Reviewing code',
  rendering: 'Rendering video',
  code_fixing: 'Auto-fixing code',
  done: 'Done',
  queued: 'Queued',
};

const statusMap = {
  starting: 'Starting',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
  queued: 'Queued',
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