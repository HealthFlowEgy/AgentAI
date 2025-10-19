/**
 * REST API service for HTTP requests
 */

import axios, { AxiosInstance, AxiosError } from 'axios'
import { Conversation, Message, UploadResponse } from '@/types/chat.types'

class APIService {
  private api: AxiosInstance

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor for auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Unauthorized - redirect to login
          localStorage.removeItem('auth_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // ==================== CHAT ====================

  async sendMessage(
    message: string,
    conversationId?: string,
    attachments?: string[]
  ): Promise<any> {
    const response = await this.api.post('/api/v1/chat/send', {
      message,
      conversation_id: conversationId,
      message_type: 'text',
      attachments,
    })
    return response.data
  }

  async getConversations(limit = 50, offset = 0): Promise<Conversation[]> {
    const response = await this.api.get('/api/v1/chat/conversations', {
      params: { limit, offset },
    })
    return response.data
  }

  async getConversationMessages(
    conversationId: string,
    limit = 100,
    offset = 0
  ): Promise<{ messages: Message[]; count: number; has_more: boolean }> {
    const response = await this.api.get(
      `/api/v1/chat/conversations/${conversationId}/messages`,
      { params: { limit, offset } }
    )
    return response.data
  }

  async deleteConversation(conversationId: string): Promise<void> {
    await this.api.delete(`/api/v1/chat/conversations/${conversationId}`)
  }

  async clearConversation(conversationId: string): Promise<void> {
    await this.api.post(`/api/v1/chat/conversations/${conversationId}/clear`)
  }

  // ==================== UPLOAD ====================

  async uploadDocument(
    file: File,
    documentType?: string
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (documentType) {
      formData.append('document_type', documentType)
    }

    const response = await this.api.post('/api/v1/upload/document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  }

  async uploadAudio(file: File, language = 'en-US'): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('language', language)

    const response = await this.api.post('/api/v1/upload/audio', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  }

  async uploadBatch(
    files: File[],
    documentType?: string
  ): Promise<UploadResponse> {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (documentType) {
      formData.append('document_type', documentType)
    }

    const response = await this.api.post('/api/v1/upload/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  }

  // ==================== MEDICAL CODES ====================

  async searchICD10(query: string, limit = 10): Promise<any[]> {
    const response = await this.api.get('/api/v1/medical-codes/icd10/search', {
      params: { q: query, limit },
    })
    return response.data
  }

  async searchCPT(query: string, limit = 10): Promise<any[]> {
    const response = await this.api.get('/api/v1/medical-codes/cpt/search', {
      params: { q: query, limit },
    })
    return response.data
  }

  async validateCodes(
    icd10Codes: string[],
    cptCodes: string[]
  ): Promise<any> {
    const response = await this.api.post('/api/v1/medical-codes/validate', {
      icd10_codes: icd10Codes,
      cpt_codes: cptCodes,
    })
    return response.data
  }

  // ==================== AUTH ====================

  async login(email: string, password: string): Promise<{ token: string }> {
    const response = await this.api.post('/api/v1/auth/login', {
      email,
      password,
    })
    return response.data
  }

  async logout(): Promise<void> {
    localStorage.removeItem('auth_token')
  }

  async getCurrentUser(): Promise<any> {
    const response = await this.api.get('/api/v1/auth/me')
    return response.data
  }

  // ==================== HEALTH ====================

  async checkHealth(): Promise<any> {
    const response = await this.api.get('/api/v1/health')
    return response.data
  }
}

export const apiService = new APIService()
