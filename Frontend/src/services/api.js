import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If token expired, try to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refreshToken');
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refreshToken,
        });

        const { accessToken } = response.data.data;
        localStorage.setItem('accessToken', accessToken);

        originalRequest.headers.Authorization = `Bearer ${accessToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// API methods
export const scraperAPI = {
  // Scrape products
  scrape: (data) => api.post('/scraper/scrape', data),
  
  // Get job status
  getJobStatus: (jobId) => api.get(`/scraper/jobs/${jobId}`),
  
  // Get all jobs
  getAllJobs: () => api.get('/scraper/jobs'),
};

export const authAPI = {
  // Register
  register: (data) => api.post('/auth/register', data),
  
  // Login
  login: (data) => api.post('/auth/login', data),
  
  // Logout
  logout: (refreshToken) => api.post('/auth/logout', { refreshToken }),
  
  // Get current user
  getMe: () => api.get('/auth/me'),
  
  // Refresh token
  refreshToken: (refreshToken) => api.post('/auth/refresh', { refreshToken }),
};

export default api;