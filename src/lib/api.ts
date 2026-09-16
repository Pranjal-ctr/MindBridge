/**
 * Kio API Client
 * Centralized Axios instance with JWT interceptors, token refresh, and 401 handling.
 */

import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

// ── Base URL ──────────────────────────────────────────────────────────
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ── Token Storage ─────────────────────────────────────────────────────
const TOKEN_KEY = 'mindbridge_access_token';
const REFRESH_TOKEN_KEY = 'mindbridge_refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// ── Axios Instance ────────────────────────────────────────────────────
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

/**
 * Timeout for a request that waits on a model, in milliseconds.
 *
 * The global 15s above is right for ordinary CRUD and deliberately unchanged.
 * It is far too short for a chat turn: the backend allows each provider call
 * `AI_REQUEST_TIMEOUT_SECONDS` (30s by default) and retries a retryable
 * failure up to `max_retries` (2), so a slow-but-successful reply can take
 * ~90s server-side.
 *
 * Aborting at 15s did not cancel any of that. The server carried on, stored
 * the AI message, and the student was shown a failure for a reply that exists
 * — visible on their next refresh. This ceiling is the server's worst case
 * plus a small margin, so the client gives up only after the server has.
 *
 * Keep in step with AI_REQUEST_TIMEOUT_SECONDS x (1 + max_retries) if either
 * changes.
 */
export const AI_REQUEST_TIMEOUT_MS = 95_000;

// ── Request Interceptor: Attach Authorization header ──────────────────
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response Interceptor: Handle 401 + Token Refresh ──────────────────
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Skip refresh for login/signup/refresh endpoints
    const skipRefreshPaths = ['/auth/login', '/auth/signup', '/auth/refresh'];
    if (
      error.response?.status !== 401 ||
      originalRequest._retry ||
      skipRefreshPaths.some((path) => originalRequest.url?.includes(path))
    ) {
      return Promise.reject(error);
    }

    // If already refreshing, queue this request
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((token) => {
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${token}`;
        }
        return api(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      clearTokens();
      window.location.href = '/login';
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });

      const newAccessToken = data.access_token;
      const newRefreshToken = data.refresh_token || refreshToken;
      setTokens(newAccessToken, newRefreshToken);

      processQueue(null, newAccessToken);

      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      }
      return api(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      clearTokens();
      window.location.href = '/login';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export default api;
