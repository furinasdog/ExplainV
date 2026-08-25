<template>
  <div class="auth-page">
    <div class="auth-card card">
      <h1>Sign in to ExplainV</h1>
      <form @submit.prevent="handleLogin">
        <label>Username</label>
        <input class="input" v-model="username" type="text" placeholder="Username" required />
        <label>Password</label>
        <input class="input" v-model="password" type="password" placeholder="Password" required />
        <p v-if="error" class="flash-error">{{ error }}</p>
        <button class="btn btn-primary submit-btn" type="submit" :disabled="loading">
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>
      <p class="auth-footer">
        New to ExplainV? <router-link to="/register">Create an account</router-link>.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '../stores/user.js';

const router = useRouter();
const user = useUserStore();

const username = ref('');
const password = ref('');
const error = ref('');
const loading = ref(false);

async function handleLogin() {
  error.value = '';
  loading.value = true;
  try {
    await user.login(username.value, password.value);
    await router.push('/');
  } catch (err) {
    error.value = err.response?.data?.error || 'Login failed';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 70vh;
}
.auth-card {
  padding: 32px;
  width: 100%;
  max-width: 308px;
}
h1 {
  font-size: 24px;
  font-weight: 300;
  text-align: center;
  margin-bottom: 16px;
  color: var(--color-text);
}
label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  margin-top: 12px;
}
.input {
  margin-top: 4px;
}
.submit-btn {
  width: 100%;
  margin-top: 16px;
  padding: 6px 16px;
  justify-content: center;
}
.flash-error {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--color-danger-subtle);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: 13px;
  border: 1px solid rgba(207, 34, 46, 0.15);
}
.auth-footer {
  text-align: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-muted);
  font-size: 14px;
  color: var(--color-text-secondary);
}
</style>