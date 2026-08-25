<template>
  <div id="app">
    <Navbar v-if="user.isLoggedIn" />
    <main class="page-container">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useUserStore } from './stores/user.js';
import Navbar from './components/Navbar.vue';

const user = useUserStore();
</script>

<style>
.page-container {
  max-width: 1012px;
  margin: 0 auto;
  padding: 24px 16px;
}
</style>