/**
 * WebSocket service for real-time chat
 */

import { Message } from '@/types/chat.types'

type MessageHandler = (message: Message) => void
type ConnectionHandler = () => void
type ErrorHandler = (error: Event) => void

export class WebSocketService {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private messageHandlers: MessageHandler[] = []
  private connectHandlers: ConnectionHandler[] = []
  private disconnectHandlers: ConnectionHandler[] = []
  private errorHandlers: ErrorHandler[] = []
  private pingInterval: NodeJS.Timeout | null = null

  constructor(url: string) {
    this.url = url
  }

  connect(userId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const wsUrl = `${this.url}/ws/${userId}`
        console.log('🔌 Connecting to WebSocket:', wsUrl)

        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          console.log('✅ WebSocket connected')
          this.reconnectAttempts = 0
          this.startPing()
          this.connectHandlers.forEach(handler => handler())
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message: Message = JSON.parse(event.data)
            console.log('📨 Received message:', message.type)
            this.messageHandlers.forEach(handler => handler(message))
          } catch (error) {
            console.error('❌ Failed to parse message:', error)
          }
        }

        this.ws.onerror = (error) => {
          console.error('❌ WebSocket error:', error)
          this.errorHandlers.forEach(handler => handler(error))
          reject(error)
        }

        this.ws.onclose = () => {
          console.log('🔌 WebSocket disconnected')
          this.stopPing()
          this.disconnectHandlers.forEach(handler => handler())
          this.handleReconnect(userId)
        }
      } catch (error) {
        console.error('❌ Failed to create WebSocket:', error)
        reject(error)
      }
    })
  }

  disconnect(): void {
    console.log('🔌 Disconnecting WebSocket')
    this.stopPing()
    
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  sendMessage(message: string, attachments?: string[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('❌ WebSocket not connected')
      throw new Error('WebSocket not connected')
    }

    const payload = {
      message,
      attachments: attachments || [],
      type: 'text',
      timestamp: new Date().toISOString()
    }

    console.log('📤 Sending message:', payload)
    this.ws.send(JSON.stringify(payload))
  }

  sendAction(action: string, data?: Record<string, any>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('❌ WebSocket not connected')
      throw new Error('WebSocket not connected')
    }

    const payload = {
      message: action,
      type: 'action',
      data,
      timestamp: new Date().toISOString()
    }

    console.log('📤 Sending action:', action)
    this.ws.send(JSON.stringify(payload))
  }

  onMessage(handler: MessageHandler): void {
    this.messageHandlers.push(handler)
  }

  onConnect(handler: ConnectionHandler): void {
    this.connectHandlers.push(handler)
  }

  onDisconnect(handler: ConnectionHandler): void {
    this.disconnectHandlers.push(handler)
  }

  onError(handler: ErrorHandler): void {
    this.errorHandlers.push(handler)
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  private handleReconnect(userId: string): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('❌ Max reconnection attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(
      `🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    )

    setTimeout(() => {
      this.connect(userId).catch(error => {
        console.error('❌ Reconnection failed:', error)
      })
    }, delay)
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000) // Ping every 30 seconds
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}

// Create singleton instance
const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
export const websocketService = new WebSocketService(wsUrl)
