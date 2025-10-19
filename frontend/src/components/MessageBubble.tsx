/**
 * Message bubble component for displaying chat messages
 */

import React from 'react'
import {
  Box,
  Paper,
  Typography,
  Avatar,
  Chip,
  Button,
  Card,
  CardContent,
} from '@mui/material'
import {
  Person as PersonIcon,
  SmartToy as BotIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { format } from 'date-fns'

import { Message, Action } from '@/types/chat.types'

interface MessageBubbleProps {
  message: Message
  onActionClick?: (action: string, data?: any) => void
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  onActionClick,
}) => {
  const isUserMessage = message.type === 'user_message'
  const isSystemMessage = message.type === 'system'
  const isErrorMessage = message.type === 'error'

  // Get message content
  const content = message.message || message.content || ''

  // Format timestamp
  const timestamp = format(new Date(message.timestamp), 'HH:mm')

  // Get agent avatar emoji
  const getAgentAvatar = () => {
    if (message.agent_avatar) return message.agent_avatar
    
    switch (message.agent_type) {
      case 'registration':
        return '📝'
      case 'verification':
        return '💳'
      case 'coding':
        return '🏥'
      case 'claims':
        return '📋'
      case 'denials':
        return '⚠️'
      case 'payment':
        return '💰'
      case 'status':
        return '🔍'
      case 'system':
        return '🏥'
      default:
        return '🤖'
    }
  }

  // Render action buttons
  const renderActions = () => {
    if (!message.actions || message.actions.length === 0) return null

    return (
      <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {message.actions.map((action: Action, index: number) => (
          <Button
            key={index}
            variant={action.variant === 'outlined' ? 'outlined' : 'contained'}
            size="small"
            startIcon={action.icon ? <span>{action.icon}</span> : null}
            onClick={() => onActionClick?.(action.action, message.data)}
            sx={{
              borderRadius: 2,
              textTransform: 'none',
              fontWeight: 500,
            }}
          >
            {action.label}
          </Button>
        ))}
      </Box>
    )
  }

  // Render data card (for structured data)
  const renderDataCard = () => {
    if (!message.data || Object.keys(message.data).length === 0) return null

    return (
      <Card sx={{ mt: 2, bgcolor: 'rgba(0,0,0,0.03)' }} variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
            📊 Data Summary
          </Typography>
          {Object.entries(message.data).map(([key, value]) => (
            <Box key={key} sx={{ mb: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {key.replace(/_/g, ' ').toUpperCase()}:
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {typeof value === 'object'
                  ? JSON.stringify(value, null, 2)
                  : String(value)}
              </Typography>
            </Box>
          ))}
        </CardContent>
      </Card>
    )
  }

  // System message styling
  if (isSystemMessage) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          mb: 2,
        }}
      >
        <Chip
          icon={<InfoIcon />}
          label={content}
          variant="outlined"
          size="small"
          sx={{ maxWidth: '80%' }}
        />
      </Box>
    )
  }

  // Error message styling
  if (isErrorMessage) {
    return (
      <Box sx={{ mb: 2 }}>
        <Paper
          elevation={1}
          sx={{
            p: 2,
            bgcolor: '#ffebee',
            border: '1px solid #ef5350',
            borderRadius: 2,
          }}
        >
          <Box display="flex" alignItems="center" gap={1}>
            <ErrorIcon color="error" />
            <Typography variant="body2" color="error">
              {content}
            </Typography>
          </Box>
        </Paper>
      </Box>
    )
  }

  // User message
  if (isUserMessage) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          mb: 2,
        }}
      >
        <Box sx={{ maxWidth: '70%' }}>
          <Paper
            elevation={1}
            sx={{
              p: 2,
              bgcolor: '#1976d2',
              color: 'white',
              borderRadius: 3,
              borderBottomRightRadius: 4,
            }}
          >
            <Typography
              variant="body1"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {content}
            </Typography>

            {/* Attachments */}
            {message.attachments && message.attachments.length > 0 && (
              <Box sx={{ mt: 1 }}>
                {message.attachments.map((attachment, index) => (
                  <Chip
                    key={index}
                    label={attachment}
                    size="small"
                    sx={{
                      bgcolor: 'rgba(255,255,255,0.2)',
                      color: 'white',
                      mr: 1,
                    }}
                  />
                ))}
              </Box>
            )}

            <Typography
              variant="caption"
              sx={{
                display: 'block',
                textAlign: 'right',
                mt: 1,
                opacity: 0.8,
              }}
            >
              {timestamp}
            </Typography>
          </Paper>
        </Box>
      </Box>
    )
  }

  // Agent message
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-start',
        mb: 3,
      }}
    >
      {/* Agent Avatar */}
      <Box sx={{ mr: 1.5, mt: 0.5 }}>
        <Avatar
          sx={{
            width: 40,
            height: 40,
            bgcolor: 'primary.main',
            fontSize: '1.2rem',
          }}
        >
          {getAgentAvatar()}
        </Avatar>
      </Box>

      <Box sx={{ maxWidth: '70%' }}>
        {/* Agent Name */}
        {message.agent_name && (
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mb: 0.5,
              fontWeight: 600,
              color: 'text.secondary',
            }}
          >
            {message.agent_name}
          </Typography>
        )}

        {/* Message Content */}
        <Paper
          elevation={1}
          sx={{
            p: 2,
            bgcolor: 'white',
            borderRadius: 3,
            borderBottomLeftRadius: 4,
          }}
        >
          {/* Markdown content */}
          <Box
            sx={{
              '& p': { margin: 0, marginBottom: 1 },
              '& p:last-child': { marginBottom: 0 },
              '& ul, & ol': { marginTop: 0.5, marginBottom: 0.5, paddingLeft: 2 },
              '& li': { marginBottom: 0.5 },
              '& strong': { fontWeight: 600 },
              '& code': {
                bgcolor: 'rgba(0,0,0,0.05)',
                padding: '2px 6px',
                borderRadius: 1,
                fontSize: '0.9em',
              },
              '& pre': {
                bgcolor: 'rgba(0,0,0,0.05)',
                padding: 1.5,
                borderRadius: 1,
                overflow: 'auto',
              },
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </Box>

          {/* Data Card */}
          {renderDataCard()}

          {/* Action Buttons */}
          {renderActions()}

          {/* Timestamp */}
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              textAlign: 'right',
              mt: 1,
              color: 'text.secondary',
            }}
          >
            {timestamp}
          </Typography>
        </Paper>

        {/* Workflow ID (if available) */}
        {message.workflow_id && (
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mt: 0.5,
              color: 'text.secondary',
            }}
          >
            Workflow: {message.workflow_id}
          </Typography>
        )}
      </Box>
    </Box>
  )
}
