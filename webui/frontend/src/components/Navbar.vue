<template>
  <nav class="navbar">
    <div class="nav-inner">
      <div class="nav-left">
        <router-link to="/" class="brand">
          <svg height="24" viewBox="0 0 16 16" width="24" fill="var(--color-text)">
            <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path>
          </svg>
          ExplainV
        </router-link>
        <router-link v-if="user.isLoggedIn" to="/create" class="nav-link">New task</router-link>
        <router-link v-if="user.isAdmin" to="/admin" class="nav-link">Admin</router-link>
      </div>
      <div class="nav-right" v-if="user.isLoggedIn">
        <button class="theme-toggle" @click="themeStore.toggle" :title="themeStore.theme === 'dark' ? 'Light mode' : 'Dark mode'">
          <svg v-if="themeStore.theme === 'dark'" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0 1.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11ZM8 0a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0v-.5A.75.75 0 0 1 8 0Zm0 13a.75.75 0 0 1 .75.75v.5a.75.75 0 0 1-1.5 0v-.5A.75.75 0 0 1 8 13Zm8-5a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1 0-1.5h.5A.75.75 0 0 1 16 8ZM3 8a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1 0-1.5h.5A.75.75 0 0 1 3 8Z"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M9.598 1.591a.75.75 0 0 1 .785-.175 7.001 7.001 0 1 1-8.967 8.967.75.75 0 0 1 .961-.96 5.5 5.5 0 0 0 7.22-7.832Z"/>
          </svg>
        </button>
        <span class="user-info">
          {{ user.username }}
          <span v-if="user.isAdmin" class="badge badge-admin">Admin</span>
        </span>
        <button class="btn btn-sm" @click="handleLogout">Sign out</button>
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