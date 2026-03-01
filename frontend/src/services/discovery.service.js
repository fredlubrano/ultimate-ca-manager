/**
 * Discovery Service v2 — scan profiles, async scanning, results, history
 */
import { apiClient, buildQueryString } from './apiClient'

export const discoveryService = {
  // ── Profiles ──────────────────────────────────────────
  getProfiles: () =>
    apiClient.get('/discovery/profiles'),

  getProfile: (id) =>
    apiClient.get(`/discovery/profiles/${id}`),

  createProfile: (data) =>
    apiClient.post('/discovery/profiles', data),

  updateProfile: (id, data) =>
    apiClient.put(`/discovery/profiles/${id}`, data),

  deleteProfile: (id) =>
    apiClient.delete(`/discovery/profiles/${id}`),

  // ── Scanning ──────────────────────────────────────────
  scanProfile: (profileId) =>
    apiClient.post(`/discovery/profiles/${profileId}/scan`),

  scan: (targets, ports = [443]) =>
    apiClient.post('/discovery/scan', { targets, ports }),

  scanSubnet: (subnet, ports = [443]) =>
    apiClient.post('/discovery/scan', { subnet, ports }),

  // ── Results ───────────────────────────────────────────
  getAll: (params = {}) =>
    apiClient.get(`/discovery${buildQueryString(params)}`),

  getStats: (profileId) =>
    apiClient.get(`/discovery/stats${buildQueryString(profileId ? { profile_id: profileId } : {})}`),

  delete: (id) =>
    apiClient.delete(`/discovery/${id}`),

  deleteAll: (profileId) =>
    apiClient.delete(`/discovery${buildQueryString(profileId ? { profile_id: profileId } : {})}`),

  // ── History ───────────────────────────────────────────
  getRuns: (params = {}) =>
    apiClient.get(`/discovery/runs${buildQueryString(params)}`),

  getRun: (id) =>
    apiClient.get(`/discovery/runs/${id}`),
}
