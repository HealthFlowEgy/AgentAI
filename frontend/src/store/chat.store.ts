/**
 * Zustand store for chat state management
 */

import { create } from 'zustand'
import { Message, Conversation, ChatState } from '@/types/chat.types'

interface ChatStore extends ChatState {
  // Actions
  addMessage: (message: Message) => void
  setMessages: (messages: Message[]) => void
  clearMessages: () => void
  setConversations: (conversations: Conversation[]) => void
  addConversation: (conversation: Conversation) => void
  removeConversation: (conversationId: string) => void
  setCurrentConversation: (conversationId: string | null) => void
  setIsConnected: (isConnected: boolean) => void
  setIsTyping: (isTyping: boolean, agent?: string) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  // Initial state
  messages: [],
  conversations: [],
  currentConversationId: null,
  isConnected: false,
  isTyping: false,
  typingAgent: null,

  // Actions
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setMessages: (messages) =>
    set(() => ({
      messages,
    })),

  clearMessages: () =>
    set(() => ({
      messages: [],
    })),

  setConversations: (conversations) =>
    set(() => ({
      conversations,
    })),

  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
    })),

  removeConversation: (conversationId) =>
    set((state) => ({
      conversations: state.conversations.filter(
        (c) => c.conversation_id !== conversationId
      ),
    })),

  setCurrentConversation: (conversationId) =>
    set(() => ({
      currentConversationId: conversationId,
    })),

  setIsConnected: (isConnected) =>
    set(() => ({
      isConnected,
    })),

  setIsTyping: (isTyping, agent) =>
    set(() => ({
      isTyping,
      typingAgent: agent || null,
    })),
}))
