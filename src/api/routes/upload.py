"""
File Upload API Route
Handles document uploads with OCR processing
Supports: Images, PDFs, audio files
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
import aiofiles
import os
from pathlib import Path
from datetime import datetime
import uuid
import logging

from src.services.ocr_service import OCRService
from src.services.speech_service import SpeechService
from src.core.auth import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])

# Initialize services
ocr_service = OCRService()
speech_service = SpeechService()

# Upload directory configuration
UPLOAD_DIR = Path("/tmp/healthflow_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# File size limits (in bytes)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES_PER_REQUEST = 5

# Allowed file types
ALLOWED_IMAGE_TYPES = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'}
ALLOWED_DOCUMENT_TYPES = {'.pdf'}
ALLOWED_AUDIO_TYPES = {'.wav', '.mp3', '.webm', '.ogg', '.m4a'}


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    user: User = Depends(get_current_user)
):
    """
    Upload document (image or PDF) for OCR processing
    
    Supported formats: JPG, PNG, BMP, TIFF, PDF
    Max size: 10 MB
    
    Document types:
    - id_card: National ID or passport
    - bill: Medical bill or invoice
    - eob: Explanation of Benefits
    - medical_record: Medical records or prescriptions
    """
    logger.info(f"📤 Document upload from user {user.id}: {file.filename}")
    
    try:
        # Validate file type
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_IMAGE_TYPES and file_extension not in ALLOWED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_extension}. "
                       f"Allowed: {', '.join(ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES)}"
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size / 1024 / 1024:.1f}MB. "
                       f"Maximum: {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{user.id}_{timestamp}_{file_id}{file_extension}"
        file_path = UPLOAD_DIR / safe_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"✅ File saved: {file_path}")
        
        # Process with OCR
        try:
            ocr_result = await ocr_service.process_file(
                str(file_path),
                document_type=document_type
            )
            
            logger.info(f"✅ OCR processing complete: {len(ocr_result['text'])} characters")
            
            return {
                'success': True,
                'file_id': file_id,
                'filename': file.filename,
                'file_size': file_size,
                'file_path': str(file_path),
                'ocr_result': {
                    'text': ocr_result['text'],
                    'confidence': ocr_result.get('confidence', 0),
                    'word_count': ocr_result.get('word_count', 0),
                    'structured_data': ocr_result.get('structured_data', {}),
                    'detected_type': ocr_result.get('detected_type', document_type)
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as ocr_error:
            logger.error(f"❌ OCR processing failed: {ocr_error}", exc_info=True)
            
            # Return partial success (file uploaded but OCR failed)
            return {
                'success': True,
                'file_id': file_id,
                'filename': file.filename,
                'file_size': file_size,
                'file_path': str(file_path),
                'ocr_result': {
                    'error': str(ocr_error),
                    'text': None
                },
                'timestamp': datetime.utcnow().isoformat()
            }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Document upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio")
async def upload_audio(
    file: UploadFile = File(...),
    language: str = Form('en-US'),
    user: User = Depends(get_current_user)
):
    """
    Upload audio file for speech-to-text transcription
    
    Supported formats: WAV, MP3, WebM, OGG, M4A
    Max size: 10 MB
    
    Languages:
    - en-US: English (US)
    - ar-EG: Arabic (Egypt)
    - ar-SA: Arabic (Saudi Arabia)
    """
    logger.info(f"🎤 Audio upload from user {user.id}: {file.filename}")
    
    try:
        # Validate file type
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio type: {file_extension}. "
                       f"Allowed: {', '.join(ALLOWED_AUDIO_TYPES)}"
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size / 1024 / 1024:.1f}MB"
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{user.id}_{timestamp}_{file_id}{file_extension}"
        file_path = UPLOAD_DIR / safe_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"✅ Audio file saved: {file_path}")
        
        # Transcribe
        try:
            transcription, confidence = await speech_service.transcribe_file(
                str(file_path),
                language=language
            )
            
            logger.info(f"✅ Transcription complete: {transcription[:50]}...")
            
            return {
                'success': True,
                'file_id': file_id,
                'filename': file.filename,
                'file_size': file_size,
                'transcription': transcription,
                'confidence': confidence,
                'language': language,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as transcription_error:
            logger.error(f"❌ Transcription failed: {transcription_error}", exc_info=True)
            
            return {
                'success': False,
                'file_id': file_id,
                'filename': file.filename,
                'error': str(transcription_error),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        finally:
            # Cleanup audio file (optional)
            try:
                os.unlink(file_path)
            except:
                pass
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Audio upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def upload_batch(
    files: List[UploadFile] = File(...),
    document_type: Optional[str] = Form(None),
    user: User = Depends(get_current_user)
):
    """
    Upload multiple documents at once
    
    Max files per request: 5
    Max size per file: 10 MB
    """
    logger.info(f"📤 Batch upload from user {user.id}: {len(files)} files")
    
    # Validate number of files
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: {len(files)}. Maximum: {MAX_FILES_PER_REQUEST}"
        )
    
    results = []
    
    for file in files:
        try:
            # Process each file
            result = await upload_document(file, document_type, user)
            results.append(result)
        
        except Exception as e:
            logger.error(f"❌ Failed to process {file.filename}: {e}")
            results.append({
                'success': False,
                'filename': file.filename,
                'error': str(e)
            })
    
    # Calculate success rate
    successful = sum(1 for r in results if r.get('success'))
    
    return {
        'success': successful > 0,
        'total_files': len(files),
        'successful': successful,
        'failed': len(files) - successful,
        'results': results,
        'timestamp': datetime.utcnow().isoformat()
    }


@router.delete("/file/{file_id}")
async def delete_file(
    file_id: str,
    user: User = Depends(get_current_user)
):
    """Delete uploaded file"""
    try:
        # Find file with this ID
        for file_path in UPLOAD_DIR.glob(f"{user.id}_*_{file_id}*"):
            os.unlink(file_path)
            logger.info(f"🗑️ Deleted file: {file_path}")
            
            return {
                'success': True,
                'message': 'File deleted successfully',
                'file_id': file_id
            }
        
        raise HTTPException(status_code=404, detail="File not found")
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Failed to delete file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
async def list_files(
    limit: int = 50,
    user: User = Depends(get_current_user)
):
    """List uploaded files for current user"""
    try:
        files = []
        
        for file_path in UPLOAD_DIR.glob(f"{user.id}_*"):
            stat = file_path.stat()
            files.append({
                'filename': file_path.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        # Sort by modified time (newest first)
        files.sort(key=lambda f: f['modified'], reverse=True)
        
        return {
            'files': files[:limit],
            'total': len(files),
            'limit': limit
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to list files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def upload_health():
    """Check upload service health"""
    return {
        'status': 'healthy',
        'upload_dir': str(UPLOAD_DIR),
        'max_file_size_mb': MAX_FILE_SIZE / 1024 / 1024,
        'max_files_per_request': MAX_FILES_PER_REQUEST,
        'supported_formats': {
            'images': list(ALLOWED_IMAGE_TYPES),
            'documents': list(ALLOWED_DOCUMENT_TYPES),
            'audio': list(ALLOWED_AUDIO_TYPES)
        }
    }
