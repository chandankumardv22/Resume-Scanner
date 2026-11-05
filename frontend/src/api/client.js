// ==============================================================================
// TECH STACK: [Axios] - Centralized Production API Client
// Handles Environment-Based Base URL, Timeouts, Auth Interceptors, & Robust Error Handling
// ==============================================================================
import axios from 'axios';

const AUTH_STORAGE_KEY = 'ra_auth';
export const DEFAULT_TIMEOUT_MS = 30000;      // 30 seconds for standard requests
export const ANALYZE_TIMEOUT_MS = 120000;    // 120 seconds for deep AI resume analysis

/**
 * Resolves the backend API base origin.
 * Priority:
 * 1. process.env.REACT_APP_API_URL (configured in .env or cloud environment)
 * 2. Fallback default: 'http://127.0.0.1:8000'
 */
export function getApiBaseUrl() {
  const raw = process.env.REACT_APP_API_URL;
  if (raw != null && String(raw).trim() !== '') {
    return String(raw).trim().replace(/\/+$/, '');
  }
  // In production browser environments without explicit API URL, default to same origin
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';
    if (!isLocal) {
      return window.location.origin;
    }
  }
  return 'http://127.0.0.1:8000';
}

// Backward-compatible alias
export const getApiOrigin = getApiBaseUrl;

/**
 * Standardized, human-friendly API error formatter.
 * Handles network failures, timeout errors, FastAPI Pydantic validation arrays,
 * and custom server error payloads.
 */
export function formatApiError(err) {
  if (!err) return 'An unexpected error occurred. Please try again.';

  if (err.code === 'ECONNABORTED' || (err.message && err.message.toLowerCase().includes('timeout'))) {
    return 'The request timed out. The server or AI model is taking longer than expected. Please try again.';
  }

  if (
    err.code === 'ERR_NETWORK' ||
    err.message === 'Network Error' ||
    (!err.response && err.request)
  ) {
    return `Unable to reach the server at ${getApiBaseUrl()}. Please make sure the backend server is running and accessible.`;
  }

  const data = err.response?.data;
  if (typeof data?.detail === 'string') return data.detail;
  if (typeof data?.error === 'string') return data.error;
  if (data?.detail?.error && typeof data.detail.error === 'string') return data.detail.error;

  if (Array.isArray(data?.detail)) {
    const messages = data.detail
      .map((item) => (typeof item === 'string' ? item : item?.msg))
      .filter(Boolean);
    if (messages.length > 0) return messages.join('; ');
  }

  if (typeof data?.message === 'string') return data.message;
  if (err.response?.status) {
    if (err.response.status === 413) return 'The uploaded file is too large. Please upload a smaller PDF (under 10MB).';
    if (err.response.status === 401) return 'Your session has expired. Please sign in again.';
    if (err.response.status === 429) return 'Rate limit exceeded. Please wait a moment before trying again.';
    return `Request failed with status code ${err.response.status}.`;
  }

  return err.message || 'Something went wrong. Please try again.';
}

// Backward-compatible alias
export const formatAuthError = formatApiError;

/**
 * Creates and configures the Axios instance.
 */
export const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: DEFAULT_TIMEOUT_MS,
  headers: {
    Accept: 'application/json',
  },
});

// Request Interceptor: automatically attaches JWT/Session Bearer token from localStorage
apiClient.interceptors.request.use(
  (config) => {
    // Dynamic base URL check in case environment was set at runtime
    if (!config.baseURL) {
      config.baseURL = getApiBaseUrl();
    }
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (saved?.token && !config.headers.Authorization) {
          config.headers.Authorization = `Bearer ${saved.token}`;
        }
      }
    } catch {
      // Ignore localStorage parse errors
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response Interceptor: handles global auth expiration
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear expired credentials
      try {
        localStorage.removeItem(AUTH_STORAGE_KEY);
      } catch {
        /* ignore */
      }
    }
    return Promise.reject(error);
  },
);

// ==============================================================================
// Centralized API Service Methods
// ==============================================================================

export const apiService = {
  // Authentication
  async register({ name, email, password, phone = '' }) {
    const res = await apiClient.post('/api/auth/register', {
      name: name.trim(),
      email: email.trim(),
      password,
      phone: phone.trim(),
    });
    return res.data;
  },

  async login({ email, password }) {
    const res = await apiClient.post('/api/auth/login', {
      email: email.trim(),
      password,
    });
    return res.data;
  },

  async getMe(token) {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await apiClient.get('/api/auth/me', { headers });
    return res.data;
  },

  async logout(token) {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await apiClient.post('/api/auth/logout', {}, { headers });
    return res.data;
  },

  // Platform Metadata & Jobs
  async getPlatformStats() {
    const res = await apiClient.get('/api/platform-stats');
    return res.data;
  },

  async getFeatures() {
    const res = await apiClient.get('/api/features');
    return res.data;
  },

  async exploreJobs(role = 'Software Engineer') {
    const res = await apiClient.get('/api/explore-jobs', {
      params: { role },
    });
    return res.data;
  },

  async fetchJobs(recommendedRoles = []) {
    const res = await apiClient.post('/api/fetch-jobs', {
      recommended_roles: recommendedRoles,
    });
    return res.data;
  },

  // Resume Analysis
  async analyzeResume(file, jobDescription = null, onUploadProgress = null) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    if (jobDescription && String(jobDescription).trim()) {
      formData.append('job_description', String(jobDescription).trim());
    }

    const res = await apiClient.post('/analyze', formData, {
      timeout: ANALYZE_TIMEOUT_MS,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
    });
    return res.data;
  },

  // Healthcheck & readiness
  async checkHealth() {
    const res = await apiClient.get('/health', { timeout: 10000 });
    return res.data;
  },
};

export default apiClient;
