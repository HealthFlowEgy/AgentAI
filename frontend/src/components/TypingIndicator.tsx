/**
 * Typing indicator component
 */

import React from 'react'
import { Box, Paper, Typography, Avatar } from '@mui/material'
import { keyframes } from '@mui/system'

interface TypingIndicatorProps {
  agentName?: string
}

// Dot animation
const bounce = keyframes`
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-10px);
  }
`

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({
  agentName = 'Assistant',
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-start',
        mb: 2,
      }}
    >
      {/* Avatar */}
      <Box sx={{ mr: 1.5, mt: 0.5 }}>
        <Avatar
          sx={{
            width: 40,
            height: 40,
            bgcolor: 'primary.main',
            fontSize: '1.2rem',
          }}
        >
          🤖
        </Avatar>
      </Box>

      <Box sx={{ maxWidth: '70%' }}>
        {/* Agent Name */}
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mb: 0.5,
            fontWeight: 600,
            color: 'text.secondary',
          }}
        >
          {agentName}
        </Typography>

        {/* Typing Indicator */}
        <Paper
          elevation={1}
          sx={{
            p: 2,
            bgcolor: 'white',
            borderRadius: 3,
            borderBottomLeftRadius: 4,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
          }}
        >
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: 'primary.main',
              animation: `${bounce} 1.4s infinite ease-in-out`,
              animationDelay: '0s',
            }}
          />
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: 'primary.main',
              animation: `${bounce} 1.4s infinite ease-in-out`,
              animationDelay: '0.2s',
            }}
          />
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: 'primary.main',
              animation: `${bounce} 1.4s infinite ease-in-out`,
              animationDelay: '0.4s',
            }}
          />
          <Typography
            variant="caption"
            sx={{ ml: 1, color: 'text.secondary' }}
          >
            typing...
          </Typography>
        </Paper>
      </Box>
    </Box>
  )
}
