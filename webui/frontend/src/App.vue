<template>
  <div id="app">
    <Navbar v-if="user.isLoggedIn" />
    <main class="page-container">
      <UserGuide v-if="showGuide" @dismiss="handleDismissGuide" />
      <router-view />
    </main>
    <AppFooter v-if="user.isLoggedIn" />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useUserStore } from './stores/user.js';
import Navbar from './components/Navbar.vue';
import AppFooter from './components/AppFooter.vue';
import UserGuide from './components/UserGuide.vue';

const user = useUserStore();

// 用户引导：非管理员用户首次登录时显示
const guideDismissed = ref(localStorage.getItem('guide_dismissed') === 'true');

const showGuide = computed(() => {
  return user.isLoggedIn && !user.isAdmin && !guideDismissed.value;
});

function handleDismissGuide() {
  guideDismissed.value = true;
  localStorage.setItem('guide_dismissed', 'true');
}

// 退出登录时重置引导状态不需要，因为用 localStorage 持久化
</script>

<style>
.page-container {
  max-width: 1012px;
  margin: 0 auto;
  padding: 24px 16px;
  min-height: calc(100vh - 48px - 120px); /* navbar + footer */
}

/* 深色模式下仅图标反色（黑→白），不影响其他元素 */
[data-theme="dark"] .brand-icon {
  filter: invert(1);
}
</style>
