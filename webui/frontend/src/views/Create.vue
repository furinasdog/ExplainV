<template>
  <div>
    <div class="page-header">
      <h2>新建任务</h2>
    </div>

    <form @submit.prevent="handleSubmit" class="form-card card">
      <section class="form-section">
        <h3>题目输入</h3>
        <label>题目文本</label>
        <textarea
          v-model="problemText"
          rows="5"
          placeholder="例如：已知直角三角形两直角边分别为3和4，求斜边长度。"
        ></textarea>
        <div class="divider"><span>或</span></div>
        <label>上传题目图片</label>
        <input type="file" accept="image/*" @change="handleImageUpload" class="file-input" />
        <img v-if="imagePreview" :src="imagePreview" class="image-preview" alt="题目图片预览" />
      </section>

      <section class="form-section">
        <h3>语音设置</h3>
        <label>参考音频（可选，用于语音克隆）</label>
        <input type="file" accept="audio/*" @change="handleAudioUpload" class="file-input" />
        <p v-if="audioName" class="hint">已选择: {{ audioName }}</p>
      </section>

      <section class="form-section">
        <h3>参数设置</h3>
        <label>画质</label>
        <select v-model="quality">
          <option value="l">低清 (480p，快速)</option>
          <option value="m">标清 (720p)</option>
          <option value="h">高清 (1080p)</option>
          <option value="k">超高清 (4K，较慢)</option>
        </select>

        <label>讲解模块</label>
        <div class="checkbox-group">
          <label v-for="s in sectionOptions" :key="s.key" class="checkbox-item">
            <input type="checkbox" :value="s.key" v-model="selectedSections" />
            {{ s.label }}
          </label>
        </div>

        <label v-if="selectedSections.includes('solution_process')" class="checkbox-item" style="margin-top: 8px;">
          <input type="checkbox" v-model="briefSolution" />
          简略解答（仅展示解题思路）
        </label>
      </section>

      <div v-if="error" class="flash-error">{{ error }}</div>

      <div class="form-actions">
        <button class="btn btn-primary" type="submit" :disabled="loading">
          {{ loading ? '提交中...' : '提交任务' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api/index.js';

const router = useRouter();

const sectionOptions = [
  { key: 'restatement', label: '题目复述' },
  { key: 'knowledge_points', label: '知识点总结' },
  { key: 'solution_process', label: '题目解答过程' },
  { key: 'answer_verification', label: '答案验证' },
  { key: 'common_mistakes', label: '易错考点' },
  { key: 'practice_methods', label: '练习方法' },
];

const problemText = ref('');
const problemImageBase64 = ref(null);
const imagePreview = ref(null);
const refAudioBase64 = ref(null);
const audioName = ref('');
const quality = ref('h');
const selectedSections = ref(sectionOptions.map((s) => s.key));
const briefSolution = ref(false);
const error = ref('');
const loading = ref(false);

function handleImageUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    problemImageBase64.value = reader.result.split(',')[1];
    imagePreview.value = reader.result;
  };
  reader.readAsDataURL(file);
}

function handleAudioUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  audioName.value = file.name;
  const reader = new FileReader();
  reader.onload = () => { refAudioBase64.value = reader.result.split(',')[1]; };
  reader.readAsDataURL(file);
}

async function handleSubmit() {
  error.value = '';
  if (!problemText.value.trim() && !problemImageBase64.value) {
    error.value = '请输入题目文本或上传题目图片';
    return;
  }
  loading.value = true;
  try {
    await api.post('/api/tasks', {
      problemText: problemText.value.trim() || null,
      problemImageBase64: problemImageBase64.value,
      refAudioBase64: refAudioBase64.value,
      quality: quality.value,
      sections: selectedSections.value,
      briefSolution: briefSolution.value,
    });
    router.push('/');
  } catch (err) {
    error.value = err.response?.data?.error || '提交失败';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}
h2 {
  font-size: 24px;
  font-weight: 600;
}
.form-card {
  padding: 24px;
}
.form-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-border-muted);
}
.form-section:last-of-type {
  border-bottom: none;
  margin-bottom: 16px;
  padding-bottom: 0;
}
h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}
label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-top: 12px;
  margin-bottom: 4px;
}
textarea {
  font-family: var(--font-mono);
  font-size: 13px;
  resize: vertical;
}
.file-input {
  font-size: 13px;
  padding: 6px 0;
  border: none;
  color: var(--color-text-secondary);
}
.image-preview {
  max-width: 100%;
  max-height: 200px;
  margin-top: 8px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}
.divider {
  display: flex;
  align-items: center;
  margin: 16px 0;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.divider::before, .divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid var(--color-border-muted);
}
.divider span {
  padding: 0 12px;
}
.hint {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 400;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-md);
}
.checkbox-item:hover {
  background: var(--color-bg-tertiary);
}
.checkbox-item input {
  width: auto;
  accent-color: var(--color-accent);
}
.flash-error {
  padding: 8px 12px;
  background: var(--color-danger-subtle);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: 13px;
  border: 1px solid rgba(207, 34, 46, 0.15);
  margin-bottom: 12px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-muted);
}
</style>
