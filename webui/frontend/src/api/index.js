import axios from 'axios';
import router from '../router/index.js';

const api = axios.create({
  baseURL: '',
  timeout: 30000,
});

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      router.push('/login');
    }
    return Promise.reject(err);
  }
);

export default api;
