/**
 * Voice recorder component with real-time visualization
 */

import React, { useState, useEffect, useRef } from 'react'
import { Box, IconButton, Typography, Paper } from '@mui/material'
import { Mic as MicIcon, Stop as StopIcon } from '@mui/icons-material'

interface VoiceRecorderProps {
  onStart: () => void
  onStop: (audioBlob: Blob) => void
  isRecording: boolean
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  onStart,
  onStop,
  isRecording,
}) => {
  const [duration, setDuration] = useState(0)
  const [audioLevel, setAudioLevel] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (isRecording) {
      startRecording()
    } else {
      stopRecording()
    }

    return () => {
      cleanup()
    }
  }, [isRecording])

  const startRecording = async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Initialize MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm',
      })

      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: 'audio/webm',
        })
        onStop(audioBlob)
        cleanup()
      }

      mediaRecorder.start()
      onStart()

      // Setup audio visualization
      setupAudioVisualization(stream)

      // Start timer
      setDuration(0)
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1)
      }, 1000)
    } catch (error) {
      console.error('❌ Failed to start recording:', error)
      alert('Failed to access microphone. Please check permissions.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
      
      // Stop all tracks
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop())
    }

    cleanup()
  }

  const setupAudioVisualization = (stream: MediaStream) => {
    // Create audio context
    const audioContext = new AudioContext()
    audioContextRef.current = audioContext

    // Create analyser
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    analyserRef.current = analyser

    // Connect stream to analyser
    const source = audioContext.createMediaStreamSource(stream)
    source.connect(analyser)

    // Start visualization loop
    visualize()
  }

  const visualize = () => {
    if (!analyserRef.current) return

    const bufferLength = analyserRef.current.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const draw = () => {
      if (!analyserRef.current) return

      animationFrameRef.current = requestAnimationFrame(draw)

      analyserRef.current.getByteFrequencyData(dataArray)

      // Calculate average audio level
      const average = dataArray.reduce((a, b) => a + b, 0) / bufferLength
      const normalizedLevel = Math.min(average / 128, 1)
      setAudioLevel(normalizedLevel)
    }

    draw()
  }

  const cleanup = () => {
    // Clear timer
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    // Cancel animation frame
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    setAudioLevel(0)
    setDuration(0)
  }

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!isRecording) return null

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'fixed',
        bottom: 100,
        left: '50%',
        transform: 'translateX(-50%)',
        p: 2,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        bgcolor: '#fff',
        borderRadius: 3,
        zIndex: 1000,
      }}
    >
      {/* Recording Indicator */}
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: '50%',
          bgcolor: '#f44336',
          animation: 'pulse 1.5s infinite',
          '@keyframes pulse': {
            '0%, 100%': { opacity: 1 },
            '50%': { opacity: 0.5 },
          },
        }}
      />

      {/* Audio Level Visualization */}
      <Box
        sx={{
          width: 100,
          height: 40,
          bgcolor: 'rgba(0,0,0,0.05)',
          borderRadius: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Audio bars */}
        {[...Array(10)].map((_, i) => (
          <Box
            key={i}
            sx={{
              width: 6,
              height: `${audioLevel * 100}%`,
              bgcolor: 'primary.main',
              mx: 0.25,
              borderRadius: 1,
              transition: 'height 0.1s',
              opacity: 0.7 + (i * 0.03),
            }}
          />
        ))}
      </Box>

      {/* Duration */}
      <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 40 }}>
        {formatDuration(duration)}
      </Typography>

      {/* Stop Button */}
      <IconButton
        color="error"
        onClick={stopRecording}
        sx={{
          bgcolor: 'rgba(244, 67, 54, 0.1)',
          '&:hover': {
            bgcolor: 'rgba(244, 67, 54, 0.2)',
          },
        }}
      >
        <StopIcon />
      </IconButton>

      {/* Hint */}
      <Typography variant="caption" color="text.secondary">
        Click stop when done
      </Typography>
    </Paper>
  )
}
