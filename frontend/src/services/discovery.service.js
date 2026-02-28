/**
 * Discovery Service — certificate network discovery API
 */
import { apiClient, buildQueryString } from './apiClient'

export const discoveryService = {
  /** Scan a list of targets */
  scan: (targets, ports = [443]) =>
    apiClient.post('/discovery/scan', { targets, ports }),

  /** Scan a CIDR subnet */
  scanSubnet: (subnet, ports = [443]) =>
    apiClient.post('/discovery/scan-subnet', { subnet, ports }),

  /** List all discovered certificates */
  getAll: (limit = 500) =>
    apiClient.get(`/discovery${buildQueryString({ limit })}`),

  /** List unknown (not in UCM) certificates */
  getUnknown: () =>
    apiClient.get('/discovery/unknown'),

  /** List expired discovered certificates */
  getExpired: () =>
    apiClient.get('/discovery/expired'),

  /** Get summary statistics */
  getStats: () =>
    apiClient.get('/discovery/stats'),

  /** Delete a single discovered certificate */
  delete: (id) =>
    apiClient.delete(`/discovery/${id}`),

  /** Delete all discovered certificates */
  deleteAll: () =>
    apiClient.delete('/discovery'),
}
