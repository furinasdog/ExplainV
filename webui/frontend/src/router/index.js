import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '../stores/user.js';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { auth: true },
  },
  {
    path: '/create',
    name: 'Create',
    component: () => import('../views/Create.vue'),
    meta: { auth: true },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminDashboard.vue'),
    meta: { auth: true, admin: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const user = useUserStore();

  if (to.meta.auth && !user.isLoggedIn) {
    return { name: 'Login' };
  }
  if (to.meta.admin && !user.isAdmin) {
    return { name: 'Dashboard' };
  }
  if (to.meta.guest && user.isLoggedIn) {
    return { name: 'Dashboard' };
  }
});

export default router;
