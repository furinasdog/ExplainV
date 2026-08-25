<template>
  <nav class="navbar">
    <div class="nav-inner">
      <div class="nav-left">
        <router-link to="/" class="brand">
          <img src="/icon.png" alt="ExplainV" class="brand-icon" />
          ExplainV
        </router-link>
        <router-link v-if="user.isLoggedIn" to="/create" class="nav-link">新建任务</router-link>
        <router-link v-if="user.isAdmin" to="/admin" class="nav-link">管理面板</router-link>
      </div>
      <div class="nav-right" v-if="user.isLoggedIn">
        <button class="theme-toggle" @click="themeStore.toggle" :title="themeStore.theme === 'dark' ? '浅色模式' : '深色模式'">
          <svg v-if="themeStore.theme === 'dark'" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0 1.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11ZM8 0a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0v-.5A.75.75 0 0 1 8 0Zm0 13a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0v-.5A.75.75 0 0 1 8 13Zm8-5a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1 0-1.5h.5A.75.75 0 0 1 16 8ZM3 8a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1 0-1.5h.5A.75.75 0 0 1 3 8Z"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M9.598 1.591a.75.75 0 0 1 .785-.175 7.001 7.001 0 1 1-8.967 8.967.75.75 0 0 1 .961-.96 5.5 5.5 0 0 0 7.22-7.832Z"/>
          </svg>
        </button>
        <span class="user-info">
          {{ user.username }}
          <span v-if="user.isAdmin" class="badge badge-admin">管理员</span>
        </span>
        <button class="btn btn-sm" @click="handleLogout">退出登录</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user.js';
import { useThemeStore } from '../stores/theme.js';

const router = useRouter();
const user = useUserStore();
const themeStore = useThemeStore();

function handleLogout() {
  user.logout();
  router.push('/login');
}
</script>

<style scoped>
.navbar {
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 100;
}
.nav-inner {
  max-width: 1012px;
  margin: 0 auto;
  padding: 0 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 48px;
}
.nav-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  text-decoration: none;
}
.brand:hover { text-decoration: none; opacity: 0.85; }
.brand-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  object-fit: contain;
}
.nav-link {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
  text-decoration: none;
  padding: 4px 8px;
  border-radius: var(--radius-md);
}
.nav-link:hover {
  color: var(--color-text);
  background: var(--color-bg-tertiary);
  text-decoration: none;
}
.nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
}
.theme-toggle:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.user-info {
  font-size: 14px;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
