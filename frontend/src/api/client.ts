import axios from 'axios';

// Configure the base HTTP client
export const apiClient = axios.create({
  // Fallback to relative /api path which will be proxied by Vite in development
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 15000, // 15 seconds timeout
});

// Request Interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Placeholder: Inject auth tokens here if needed
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Global error handler
    console.error('API Error:', error?.response?.data || error.message);
    return Promise.reject(error);
  }
);
