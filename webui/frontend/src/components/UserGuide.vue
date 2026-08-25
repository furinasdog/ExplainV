<template>
  <div class="guide-panel card">
    <div class="guide-header">
      <h3>👋 欢迎使用 ExplainV</h3>
      <button class="guide-close" @click="$emit('dismiss')" title="关闭引导">✕</button>
    </div>
    <div class="guide-body">
      <p class="guide-intro">ExplainV 是一个 AI 题解视频生成器，可以将数学/理科题目转化为动画讲解视频。</p>
      <div class="guide-steps">
        <div class="guide-step">
          <span class="step-num">1</span>
          <div class="step-content">
            <strong>创建任务</strong>
            <p>点击导航栏的「新建任务」，输入或上传题目（支持文字和图片）</p>
          </div>
        </div>
        <div class="guide-step">
          <span class="step-num">2</span>
          <div class="step-content">
            <strong>选择参数</strong>
            <p>设置画质和讲解模块，可选上传参考音频进行语音克隆</p>
          </div>
        </div>
        <div class="guide-step">
          <span class="step-num">3</span>
          <div class="step-content">
            <strong>等待生成</strong>
            <p>系统将自动分配计算资源，如当前满载则进入排队（最多20个任务并行）</p>
          </div>
        </div>
        <div class="guide-step">
          <span class="step-num">4</span>
          <div class="step-content">
            <strong>获取结果</strong>
            <p>生成完成后可在「我的任务」中下载视频和查看讲解内容</p>
          </div>
        </div>
      </div>
      <div class="guide-tips">
        <p>💡 <strong>温馨提示：</strong>每个账号同时只能有一个运行中的任务。任务完成后才能创建新任务。</p>
      </div>
    </div>
    <div class="guide-footer">
      <button class="btn btn-primary" @click="$emit('dismiss')">我知道了，开始使用</button>
    </div>
  </div>
</template>

<script setup>
defineEmits(['dismiss']);
</script>

<style scoped>
.guide-panel {
  margin-bottom: 20px;
  padding: 20px;
  border: 1px solid var(--color-accent-emphasis, #1f6feb);
  background: var(--color-accent-subtle, rgba(31, 111, 235, 0.04));
}
.guide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.guide-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}
.guide-close {
  background: none;
  border: none;
  font-size: 16px;
  color: var(--color-text-tertiary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-md);
}
.guide-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.guide-intro {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
  line-height: 1.5;
}
.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}
.guide-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.step-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 50%;
  background: var(--color-accent-emphasis, #1f6feb);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.step-content strong {
  font-size: 14px;
  display: block;
  margin-bottom: 2px;
}
.step-content p {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.4;
}
.guide-tips {
  padding: 10px 14px;
  background: var(--color-bg-inset, rgba(0,0,0,0.03));
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}
.guide-tips p {
  margin: 0;
}
.guide-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-muted);
}
</style>
