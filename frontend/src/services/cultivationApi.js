import apiClient from './apiClient';

const base = (habitId) => `/cultivation/habits/${habitId}`;

export const fetchOverviewApi = () => apiClient.get('/cultivation/overview');
export const fetchRankApi = () => apiClient.get('/cultivation/rank');
export const fetchStatsApi = (days = 168) => apiClient.get(`/cultivation/stats?days=${days}`);
export const fetchProgressApi = (days = 90) => apiClient.get(`/cultivation/progress?days=${days}`);
export const fetchHabitsApi = (includeArchived = false) =>
  apiClient.get(`/cultivation/habits${includeArchived ? '?include_archived=true' : ''}`);
export const fetchHabitApi = (habitId, historyDays = 90) =>
  apiClient.get(`${base(habitId)}?history_days=${historyDays}`);

export const createHabitApi = (payload) => apiClient.post('/cultivation/habits', payload);
export const logSleepApi = (habitId, payload) => apiClient.post(`${base(habitId)}/sleep`, payload);
export const markDayApi = (habitId, payload) => apiClient.post(`${base(habitId)}/marks`, payload);
export const startModeApi = (habitId, payload) => apiClient.post(`${base(habitId)}/modes/start`, payload);
export const endModeApi = (habitId, payload) => apiClient.post(`${base(habitId)}/modes/end`, payload);
export const changeStageApi = (habitId, payload) => apiClient.post(`${base(habitId)}/stage`, payload);
export const changeLevelApi = (habitId, payload) => apiClient.post(`${base(habitId)}/level`, payload);
export const startNewAttemptApi = (habitId, payload) => apiClient.post(`${base(habitId)}/attempt`, payload);
export const createVersionApi = (habitId, payload) => apiClient.post(`${base(habitId)}/versions`, payload);
export const archiveHabitApi = (habitId) => apiClient.post(`${base(habitId)}/archive`);
export const unarchiveHabitApi = (habitId) => apiClient.post(`${base(habitId)}/unarchive`);
