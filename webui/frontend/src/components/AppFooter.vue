<template>
  <footer class="app-footer">
    <div class="footer-inner">
      <div class="footer-slogan">
        <span class="slogan-text">为世界上所有美好而战！</span>
      </div>
      <div class="footer-info">
        <div class="footer-team">
          <span class="team-label">团队</span>
          <span class="team-name">Anti-Entropy</span>
        </div>
        <div class="footer-divider"></div>
        <div class="footer-opensource">
          <span>本项目已在</span>
          <a href="https://github.com/Anti-Entropy/ExplainV" target="_blank" rel="noopener">GitHub</a>
          <span>开源</span>
        </div>
        <div class="footer-divider"></div>
        <div class="footer-thanks">
          <span>致谢</span>
          <a href="https://www.aliyun.com" target="_blank" rel="noopener">阿里云</a>
          <span>提供基础设施支持</span>
        </div>
      </div>
      <div class="footer-copyright">
        © {{ currentYear }} Anti-Entropy · ExplainV
      </div>
    </div>
  </footer>
</template>

<script setup>
const currentYear = new Date().getFullYear();
</script>

<style scoped>
.app-footer {
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  margin-top: 48px;
  padding: 24px 16px;
}
.footer-inner {
  max-width: 1012px;
  margin: 0 auto;
  text-align: center;
}
.footer-slogan {
  margin-bottom: 16px;
}
.slogan-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: 1px;
}
.footer-info {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.footer-team {
  display: flex;
  align-items: center;
  gap: 6px;
}
.team-label {
  color: var(--color-text-tertiary);
}
.team-name {
  font-weight: 600;
  color: var(--color-text-link);
}
.footer-divider {
  width: 1px;
  height: 14px;
  background: var(--color-border);
}
.footer-opensource,
.footer-thanks {
  display: flex;
  align-items: center;
  gap: 4px;
}
.footer-opensource a,
.footer-thanks a {
  color: var(--color-text-link);
  text-decoration: none;
}
.footer-opensource a:hover,
.footer-thanks a:hover {
  text-decoration: underline;
}
.footer-copyright {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
</style>
