import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(localStorage.getItem('theme') || 'dark');

  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('theme', t);
    theme.value = t;
  }

  function toggle() {
    applyTheme(theme.value === 'dark' ? 'light' : 'dark');
  }

  // Apply on init
  applyTheme(theme.value);

  return { theme, toggle };
});