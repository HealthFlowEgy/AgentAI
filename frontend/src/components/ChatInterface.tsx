/**
 * Main chat interface component
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  CircularProgress,
  Alert,
  Snackbar,
} from '@mui/material'
import {
  Send as SendIcon,
  AttachFile as AttachFileIcon,
  Mic as MicIcon,
  Stop as StopIcon,
} from '@mui/icons-material'

import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'
import { VoiceRecorder } from './VoiceRecorder'
import { FileUploader } from './FileUploader'

import { websocketService } from '@/services/websocket.service'
import { apiService } from '@/services/api.service'
import { useChatStore } from '@/store/chat.store'
import { Message } from '@/types/chat.types'

export const ChatInterface: React.FC = () => {
  const [inputValue, setInputValue] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [showUploader, setShowUploader] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const {
    messages,
    isConnected,
    isTyping,
    typingAgent,
    addMessage,
    setIsConnected,
    setIsTyping,
  } = useChatStore()

  // Initialize WebSocket connection
  useEffect(() => {
    const initializeChat = async () => {
      try {
        const user = await apiService.getCurrentUser()
        
        await websocketService.connect(user.id)
        
        websocketService.onMessage((message: Message) => {
          console.log('📨 New message:', message)
          
          if (message.type === 'typing') {
            setIsTyping(message.is_typing || false, message.agent_name)
          } else {
            addMessage(message)
            setIsTyping(false)
          }
        })

        websocketService.onConnect(() => {
          console.log('✅ Connected to chat')
          setIsConnected(true)
          setError(null)
        })

        websocketService.onDisconnect(() => {
          console.log('❌ Disconnected from chat')
          setIsConnected(false)
          setError('Connection lost. Reconnecting...')
        })

        websocketService.onError((error) => {
          console.error('❌ WebSocket error:', error)
          setError('Connection error. Please refresh the page.')
        })

        setIsInitializing(false)
      } catch (error) {
        console.error('❌ Failed to initialize chat:', error)
        setError('Failed to connect to chat. Please try again.')
        setIsInitializing(false)
      }
    }

    initializeChat()

    return () => {
      websocketService.disconnect()
    }
  }, [])

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSendMessage = () => {
    if (!inputValue.trim() || !isConnected) return

    try {
      websocketService.sendMessage(inputValue)
      setInputValue('')
      setError(null)
    } catch (error) {
      console.error('❌ Failed to send message:', error)
      setError('Failed to send message. Please try again.')
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleVoiceStart = () => {
    setIsRecording(true)
  }

  const handleVoiceStop = async (audioBlob: Blob) => {
    setIsRecording(false)

    try {
      const file = new File([audioBlob], 'voice.webm', { type: 'audio/webm' })
      const response = await apiService.uploadAudio(file)

      if (response.success && response.transcription) {
        setInputValue(response.transcription)
      } else {
        setError('Failed to transcribe audio. Please try again.')
      }
    } catch (error) {
      console.error('❌ Voice transcription failed:', error)
      setError('Voice transcription failed. Please try again.')
    }
  }

  const handleFileUpload = async (files: File[]) => {
    try {
      setShowUploader(false)

      for (const file of files) {
        const response = await apiService.uploadDocument(file)

        if (response.success) {
          // Send OCR result as message
          const ocrText = response.ocr_result?.text || ''
          const structuredData = response.ocr_result?.structured_data

          let message = `📎 Uploaded: ${file.name}\n\n`
          
          if (ocrText) {
            message += `📄 **Extracted Text:**\n${ocrText.substring(0, 500)}${ocrText.length > 500 ? '...' : ''}\n\n`
          }

          if (structuredData && Object.keys(structuredData).length > 0) {
            message += `📊 **Extracted Data:**\n${JSON.stringify(structuredData, null, 2)}`
          }

          websocketService.sendMessage(message, [response.file_id])
        } else {
          setError(`Failed to upload ${file.name}`)
        }
      }
    } catch (error) {
      console.error('❌ File upload failed:', error)
      setError('File upload failed. Please try again.')
    }
  }

  const handleActionClick = (action: string, data?: any) => {
    websocketService.sendAction(action, data)
  }

  if (isInitializing) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        height="100vh"
      >
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Connecting to HealthFlow...</Typography>
      </Box>
    )
  }

  return (
    <Box
      sx={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: '#f5f5f5',
      }}
    >
      {/* Header */}
      <Paper
        elevation={2}
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderRadius: 0,
        }}
      >
        <Box display="flex" alignItems="center">
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            🏥 HealthFlow RCM Assistant
          </Typography>
          <Box
            sx={{
              ml: 2,
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: isConnected ? '#4caf50' : '#f44336',
            }}
          />
          <Typography variant="body2" sx={{ ml: 1, color: 'text.secondary' }}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </Typography>
        </Box>
      </Paper>

      {/* Messages Area */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          p: 2,
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'rgba(0,0,0,0.2)',
            borderRadius: '4px',
          },
        }}
      >
        {messages.length === 0 && !isTyping && (
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            height="100%"
          >
            <Typography variant="body1" color="text.secondary">
              Start a conversation with HealthFlow Assistant
            </Typography>
          </Box>
        )}

        {messages.map((message) => (
          <MessageBubble
            key={message.message_id}
            message={message}
            onActionClick={handleActionClick}
          />
        ))}

        {isTyping && <TypingIndicator agentName={typingAgent || 'Assistant'} />}

        <div ref={messagesEndRef} />
      </Box>

      {/* Input Area */}
      <Paper
        elevation={3}
        sx={{
          p: 2,
          borderRadius: 0,
        }}
      >
        <Box display="flex" alignItems="flex-end" gap={1}>
          <IconButton
            color="primary"
            onClick={() => setShowUploader(true)}
            disabled={!isConnected}
          >
            <AttachFileIcon />
          </IconButton>

          <TextField
            fullWidth
            multiline
            maxRows={4}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message... (Shift+Enter for new line)"
            disabled={!isConnected || isRecording}
            variant="outlined"
            size="small"
          />

          {isRecording ? (
            <VoiceRecorder
              onStart={handleVoiceStart}
              onStop={handleVoiceStop}
              isRecording={isRecording}
            />
          ) : (
            <IconButton
              color="primary"
              onClick={() => setIsRecording(true)}
              disabled={!isConnected}
            >
              <MicIcon />
            </IconButton>
          )}

          <IconButton
            color="primary"
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || !isConnected}
          >
            <SendIcon />
          </IconButton>
        </Box>
      </Paper>

      {/* File Uploader Modal */}
      {showUploader && (
        <FileUploader
          onUpload={handleFileUpload}
          onClose={() => setShowUploader(false)}
        />
      )}

      {/* Error Snackbar */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setError(null)}
          severity="error"
          sx={{ width: '100%' }}
        >
          {error}
        </Alert>
      </Snackbar>
    </Box>
  )
}
