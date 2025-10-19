/**
 * File uploader component with drag & drop
 */

import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  LinearProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
} from '@mui/material'
import {
  CloudUpload as UploadIcon,
  InsertDriveFile as FileIcon,
  Delete as DeleteIcon,
  Image as ImageIcon,
  PictureAsPdf as PdfIcon,
} from '@mui/icons-material'

interface FileUploaderProps {
  onUpload: (files: File[]) => void
  onClose: () => void
}

export const FileUploader: React.FC<FileUploaderProps> = ({
  onUpload,
  onClose,
}) => {
  const [files, setFiles] = useState<File[]>([])
  const [documentType, setDocumentType] = useState<string>('')
  const [isUploading, setIsUploading] = useState(false)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prev) => [...prev, ...acceptedFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'],
      'application/pdf': ['.pdf'],
    },
    maxSize: 10 * 1024 * 1024, // 10 MB
    multiple: true,
  })

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) return

    setIsUploading(true)

    try {
      await onUpload(files)
      onClose()
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setIsUploading(false)
    }
  }

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) {
      return <ImageIcon color="primary" />
    } else if (file.type === 'application/pdf') {
      return <PdfIcon color="error" />
    } else {
      return <FileIcon />
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <Dialog
      open
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2 },
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <UploadIcon />
          <Typography variant="h6">Upload Documents</Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        {/* Document Type Selector */}
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>Document Type (Optional)</InputLabel>
          <Select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
            label="Document Type (Optional)"
          >
            <MenuItem value="">Auto-detect</MenuItem>
            <MenuItem value="id_card">National ID / Passport</MenuItem>
            <MenuItem value="bill">Medical Bill</MenuItem>
            <MenuItem value="eob">Explanation of Benefits</MenuItem>
            <MenuItem value="medical_record">Medical Record</MenuItem>
          </Select>
        </FormControl>

        {/* Drag & Drop Zone */}
        <Box
          {...getRootProps()}
          sx={{
            border: '2px dashed',
            borderColor: isDragActive ? 'primary.main' : 'grey.300',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            bgcolor: isDragActive ? 'rgba(25, 118, 210, 0.05)' : 'transparent',
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              borderColor: 'primary.main',
              bgcolor: 'rgba(25, 118, 210, 0.02)',
            },
          }}
        >
          <input {...getInputProps()} />
          <UploadIcon
            sx={{
              fontSize: 48,
              color: isDragActive ? 'primary.main' : 'grey.400',
              mb: 1,
            }}
          />
          <Typography variant="body1" gutterBottom>
            {isDragActive
              ? 'Drop files here...'
              : 'Drag & drop files here, or click to select'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Supported: Images (JPG, PNG, TIFF) and PDF • Max 10 MB per file
          </Typography>
        </Box>

        {/* File List */}
        {files.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Selected Files ({files.length})
            </Typography>
            <List dense>
              {files.map((file, index) => (
                <ListItem
                  key={index}
                  secondaryAction={
                    <IconButton
                      edge="end"
                      onClick={() => removeFile(index)}
                      disabled={isUploading}
                    >
                      <DeleteIcon />
                    </IconButton>
                  }
                  sx={{
                    bgcolor: 'rgba(0,0,0,0.02)',
                    borderRadius: 1,
                    mb: 0.5,
                  }}
                >
                  <ListItemIcon>{getFileIcon(file)}</ListItemIcon>
                  <ListItemText
                    primary={file.name}
                    secondary={formatFileSize(file.size)}
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Upload Progress */}
        {isUploading && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress />
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 1, display: 'block', textAlign: 'center' }}
            >
              Uploading and processing files...
            </Typography>
          </Box>
        )}

        {/* Info Alert */}
        <Alert severity="info" sx={{ mt: 2 }}>
          📄 Files will be automatically processed with OCR to extract text and
          data. This may take a few seconds per file.
        </Alert>
      </DialogContent>

      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button onClick={onClose} disabled={isUploading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleUpload}
          disabled={files.length === 0 || isUploading}
          startIcon={<UploadIcon />}
        >
          Upload {files.length > 0 && `(${files.length})`}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
