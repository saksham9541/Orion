import axios from 'axios';
import { getStoredToken, getStoredEmail, setStoredToken } from '@/state/AppState';

// Base API and WebSocket URLs derived from Vite environment variable
export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
export const WS_BASE = API_BASE.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');

export const getWsNotificationsUrl = (token) => {
  return `${WS_BASE}/ws/notifications?token=${encodeURIComponent(token)}`;
};

/**
 * Shared login helper to avoid duplicated fetch/axios logic across the frontend.
 */
export async function loginApi(email, password = 'password123') {
  const res = await axios.post(`${API_BASE}/api/auth/login`, {
    email,
    password,
  });
  return res.data;
}

const api = axios.create({
  baseURL: `${API_BASE}/api`,
});

// Token management: use stored token from login, with lazy refresh
let tokenPromise = null;

async function ensureToken() {
  // First try the token saved during login
  const stored = getStoredToken();
  if (stored) return stored;

  // Fallback: fetch a new token (handles case where user refreshed but token expired)
  if (tokenPromise) return tokenPromise;

  const email = getStoredEmail() || 'admin@railopt.gov.in';
  tokenPromise = loginApi(email, 'password123')
    .then((data) => {
      const token = data.access_token;
      setStoredToken(token);
      return token;
    })
    .catch(() => {
      // Clear so next call retries instead of returning null forever
      tokenPromise = null;
      return null;
    });

  return tokenPromise;
}

// Request interceptor: attach Bearer token
api.interceptors.request.use(async (config) => {
  const token = await ensureToken();
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: on 401, clear cached token and retry once
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      // Clear cached token so ensureToken fetches a fresh one
      setStoredToken(null);
      tokenPromise = null;
      const token = await ensureToken();
      if (token) {
        original.headers['Authorization'] = `Bearer ${token}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  }
);

export const fetchTasks = (filters) => api.get('/tasks', { params: filters });
export const fetchTask = (id) => api.get(`/tasks/${id}`);
export const importTasks = (data) => api.post('/tasks/import', data);
export const updateTaskStatus = (id, data) => api.put(`/tasks/${id}/status`, data);

export const generatePlan = (config) => api.post('/plans/generate', config);
export const fetchPlans = () => api.get('/plans');
export const fetchPlan = (id) => api.get(`/plans/${id}`);
export const fetchBriefing = (planId) => api.get(`/plans/${planId}/briefing`);

export const simulatePlan = (planId) => api.post(`/plans/${planId}/simulate`);
export const queryNL = (question, planId) => api.post('/query', { question, planId });
export const replan = (planId, newTask) => api.post(`/plans/${planId}/replan`, { newTask });

export const fetchCorridors = () => api.get('/corridors');
export const fetchAlerts = () => api.get('/alerts');
export const fetchDashboardStats = () => api.get('/dashboard/stats');
export const setupDemo = () => api.post('/demo/setup');

export const approvePlan = (planId, data) => api.post(`/plans/${planId}/approve`, data);
export const rejectPlan = (planId, data) => api.post(`/plans/${planId}/reject`, data);
export const modifyPlan = (planId, data) => api.post(`/plans/${planId}/modify`, data);
export const importTimetable = (data) => api.post('/timetable/import', data);
export const fetchTaskAnalysis = (taskId) => api.get(`/tasks/${taskId}/analysis`);
export const fetchMapBlocks = (planId) => api.get('/map/blocks', { params: { plan_id: planId } });

// New features
export const submitComplaint = (data) => api.post('/tasks/complaint', data);
export const fetchLiveTrains = () => api.get('/trains/live');
export const syncLiveTrains = () => api.post('/trains/live/sync');

// Multi-Agent System
export const fetchAgentsStatus = () => api.get('/agents/status');
export const triggerAgentNegotiation = (horizon = 'WEEKLY') => api.post('/agents/negotiate', { horizon });
export const scanEarlyWarnings = () => api.post('/agents/early-warning/scan');

export default api;
