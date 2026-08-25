import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '../api/index.js';

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '');
  const username = ref(localStorage.getItem('username') || '');
  const role = ref(localStorage.getItem('role') || 'user');

  const isLoggedIn = computed(() => !!token.value);
  const isAdmin = computed(() => role.value === 'admin');

  async function login(user, pass) {
    const { data } = await api.post('/api/auth/login', {
      username: user,
      password: pass,
    });
    token.value = data.token;
    username.value = data.username;
    role.value = data.role || 'user';
    localStorage.setItem('token', data.token);
    localStorage.setItem('username', data.username);
    localStorage.setItem('role', data.role || 'user');
    api.defaults.headers.common['Authorization'] = `Bearer ${data.token}`;
  }

  async function register(user, pass) {
    const { data } = await api.post('/api/auth/register', {
      username: user,
      password: pass,
    });
    token.value = data.token;
    username.value = data.username;
    role.value = data.role || 'user';
    localStorage.setItem('token', data.token);
    localStorage.setItem('username', data.username);
    localStorage.setItem('role', data.role || 'user');
    api.defaults.headers.common['Authorization'] = `Bearer ${data.token}`;
  }

  function logout() {
    token.value = '';
    username.value = '';
    role.value = 'user';
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    delete api.defaults.headers.common['Authorization'];
  }

  // Restore auth on load
  if (token.value) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
  }

  return { token, username, role, isLoggedIn, isAdmin, login, register, logout };
});
