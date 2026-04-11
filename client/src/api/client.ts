import axios from 'axios';
import type { Media, Progress, AppSettings } from '../types';

// In dev, Vite proxies /api → localhost:3001
const api = axios.create({ baseURL: '/api' });

export const mediaApi = {
  getAll: (params?: { type?: string; genre?: string }) =>
    api.get<Media[]>('/media', { params }).then(r => r.data),

  getOne: (id: number) =>
    api.get<Media>(`/media/${id}`).then(r => r.data),

  getFeatured: () =>
    api.get<Media | null>('/media/featured').then(r => r.data),

  getGenres: () =>
    api.get<string[]>('/media/genres').then(r => r.data),

  refresh: (id: number) =>
    api.post<Media>(`/media/${id}/refresh`).then(r => r.data),

  delete: (id: number) =>
    api.delete(`/media/${id}`).then(r => r.data),
};

export const searchApi = {
  query: (q: string, type?: string) =>
    api.get<Media[]>('/search', { params: { q, type } }).then(r => r.data),
};

export const streamUrl = (id: number) => `/api/stream/${id}`;

export const progressApi = {
  getAll: () =>
    api.get<(Media & { position_seconds: number; duration_seconds: number })[]>('/progress').then(r => r.data),

  get: (mediaId: number) =>
    api.get<Progress>(`/progress/${mediaId}`).then(r => r.data),

  save: (mediaId: number, positionSeconds: number, durationSeconds: number) =>
    api.post(`/progress/${mediaId}`, { position_seconds: positionSeconds, duration_seconds: durationSeconds }),
};

export const settingsApi = {
  get: () =>
    api.get<AppSettings>('/settings').then(r => r.data),

  save: (data: Partial<{ media_dirs: string[]; tmdb_api_key: string; tmdb_image_base: string }>) =>
    api.post<{ ok: boolean; settings: AppSettings }>('/settings', data).then(r => r.data),
};

export const scanApi = {
  start: () =>
    api.post<{ ok: boolean; message: string; dirs: string[] }>('/scan').then(r => r.data),
};
