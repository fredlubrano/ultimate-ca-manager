/**
 * EST (Enrollment over Secure Transport) Service
 */
import { apiClient } from './apiClient'

export const estService = {
  async getConfig() {
    return apiClient.get('/est/config')
  },

  async updateConfig(data) {
    return apiClient.patch('/est/config', data)
  },

  async getStats() {
    return apiClient.get('/est/stats')
  }
}
