/**
 * Type definitions for chat system
 */

export interface Message {
  message_id: string
  type: 'user_message' | 'agent_message' | 'typing' | 'system' | 'error' | 'workflow_update'
  message?: string
  content?: string
  agent_name?: string
  agent_type?: string
  agent_avatar?: string
  data?: Record<string, any>
  actions?: Action[]
  attachments?: Attachment[]
  workflow_id?: string
  timestamp: string
  is_typing?: boolean
}

export interface Action {
  label: string
  action: string
  icon?: string
  variant?: 'primary' | 'secondary' | 'outlined'
}

export interface Attachment {
  id: string
  filename: string
  type: 'image' | 'pdf' | 'audio' | 'document'
  url?: string
  size: number
  thumbnail?: string
}

export interface Conversation {
  conversation_id: string
  user_id: string
  title?: string
  created_at: string
  updated_at: string
  message_count: number
  status: string
  last_message?: Message
}

export interface ChatState {
  messages: Message[]
  conversations: Conversation[]
  currentConversationId: string | null
  isConnected: boolean
  isTyping: boolean
  typingAgent: string | null
}

export interface OCRResult {
  text: string
  confidence: number
  word_count: number
  structured_data: Record<string, any>
  detected_type?: string
}

export interface UploadResponse {
  success: boolean
  file_id: string
  filename: string
  file_size: number
  file_path?: string
  ocr_result?: OCRResult
  transcription?: string
  error?: string
  timestamp: string
}

export interface User {
  id: string
  email: string
  name: string
  role: string
  avatar?: string
}
