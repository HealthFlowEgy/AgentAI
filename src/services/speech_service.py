"""
Speech-to-Text Service
Converts voice recordings to text using Google Speech Recognition
Supports: WebM, MP3, WAV, OGG audio formats
"""

import speech_recognition as sr
import base64
import tempfile
import os
from pydub import AudioSegment
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SpeechService:
    """Speech-to-text transcription service"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
        # Adjust for ambient noise
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8
        self.recognizer.operation_timeout = None
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.5
    
    async def transcribe(
        self,
        audio_data: str,
        format: str = 'webm',
        language: str = 'en-US'
    ) -> str:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Base64 encoded audio data
            format: Audio format (webm, mp3, wav, ogg)
            language: Language code (en-US, ar-EG, ar-SA)
        
        Returns:
            Transcribed text
        """
        logger.info(f"🎤 Transcribing audio: format={format}, language={language}")
        
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(
                suffix=f'.{format}',
                delete=False
            ) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_path = temp_audio.name
            
            try:
                # Convert to WAV if needed
                if format.lower() != 'wav':
                    wav_path = await self._convert_to_wav(temp_path, format)
                    os.unlink(temp_path)
                    temp_path = wav_path
                
                # Transcribe using multiple methods (fallback chain)
                text = await self._transcribe_with_fallback(temp_path, language)
                
                logger.info(f"✅ Transcription successful: {text[:50]}...")
                return text
            
            finally:
                # Cleanup temporary files
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}", exc_info=True)
            raise
    
    async def _transcribe_with_fallback(
        self,
        wav_path: str,
        language: str
    ) -> str:
        """
        Transcribe with multiple fallback options
        
        Priority:
        1. Google Speech Recognition (requires internet)
        2. Sphinx (offline, lower accuracy)
        """
        with sr.AudioFile(wav_path) as source:
            # Adjust for ambient noise
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            # Record audio
            audio = self.recognizer.record(source)
            
            # Try Google Speech Recognition first
            try:
                text = self.recognizer.recognize_google(
                    audio,
                    language=language,
                    show_all=False
                )
                logger.info("✅ Google Speech Recognition successful")
                return text
            
            except sr.UnknownValueError:
                logger.warning("⚠️ Google Speech Recognition could not understand audio")
                
                # Try with different language if Arabic
                if language.startswith('ar'):
                    try:
                        text = self.recognizer.recognize_google(
                            audio,
                            language='en-US',
                            show_all=False
                        )
                        logger.info("✅ Fallback to English successful")
                        return text
                    except:
                        pass
                
                # Fallback to Sphinx (offline)
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                    logger.info("✅ Sphinx recognition successful (offline)")
                    return text if text else "[Speech not clear enough to transcribe]"
                except:
                    return "[Could not transcribe audio - please try speaking more clearly]"
            
            except sr.RequestError as e:
                logger.error(f"❌ Google Speech Recognition service error: {e}")
                
                # Fallback to Sphinx (offline)
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                    logger.info("✅ Sphinx recognition successful (offline fallback)")
                    return text if text else "[Speech not clear enough to transcribe]"
                except Exception as sphinx_error:
                    logger.error(f"❌ Sphinx recognition also failed: {sphinx_error}")
                    return "[Transcription service unavailable - please try again later]"
            
            except Exception as e:
                logger.error(f"❌ Unexpected transcription error: {e}", exc_info=True)
                return f"[Transcription error: {str(e)}]"
    
    async def _convert_to_wav(self, input_path: str, input_format: str) -> str:
        """
        Convert audio to WAV format optimized for speech recognition
        
        Args:
            input_path: Path to input audio file
            input_format: Input format (webm, mp3, ogg, etc.)
        
        Returns:
            Path to converted WAV file
        """
        logger.info(f"🔄 Converting {input_format} to WAV format")
        
        try:
            # Load audio using pydub
            audio = AudioSegment.from_file(input_path, format=input_format)
            
            # Convert to mono if stereo
            if audio.channels > 1:
                audio = audio.set_channels(1)
            
            # Set sample rate to 16000 Hz (optimal for speech recognition)
            audio = audio.set_frame_rate(16000)
            
            # Set sample width to 16-bit
            audio = audio.set_sample_width(2)
            
            # Normalize audio levels
            audio = audio.normalize()
            
            # Generate output path
            wav_path = input_path.rsplit('.', 1)[0] + '.wav'
            
            # Export as WAV
            audio.export(
                wav_path,
                format='wav',
                parameters=[
                    '-ar', '16000',  # Sample rate
                    '-ac', '1',      # Mono
                    '-sample_fmt', 's16'  # 16-bit
                ]
            )
            
            logger.info(f"✅ Conversion successful: {wav_path}")
            return wav_path
        
        except Exception as e:
            logger.error(f"❌ Audio conversion failed: {e}", exc_info=True)
            raise
    
    async def transcribe_file(
        self,
        file_path: str,
        language: str = 'en-US'
    ) -> Tuple[str, float]:
        """
        Transcribe audio file directly (without base64 encoding)
        
        Args:
            file_path: Path to audio file
            language: Language code
        
        Returns:
            Tuple of (transcribed_text, confidence_score)
        """
        logger.info(f"🎤 Transcribing file: {file_path}")
        
        try:
            # Get file format
            file_extension = Path(file_path).suffix.lower().lstrip('.')
            
            # Convert to WAV if needed
            if file_extension != 'wav':
                wav_path = await self._convert_to_wav(file_path, file_extension)
            else:
                wav_path = file_path
            
            # Transcribe
            with sr.AudioFile(wav_path) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.record(source)
                
                try:
                    # Get detailed results with confidence
                    result = self.recognizer.recognize_google(
                        audio,
                        language=language,
                        show_all=True
                    )
                    
                    if result and 'alternative' in result:
                        best_result = result['alternative'][0]
                        text = best_result.get('transcript', '')
                        confidence = best_result.get('confidence', 0.0)
                    else:
                        text = self.recognizer.recognize_google(audio, language=language)
                        confidence = 1.0  # Default confidence when not provided
                    
                    logger.info(f"✅ Transcription: '{text}' (confidence: {confidence:.2f})")
                    return text, confidence
                
                except sr.UnknownValueError:
                    logger.warning("⚠️ Could not understand audio")
                    return "[Speech not clear]", 0.0
                
                except sr.RequestError as e:
                    logger.error(f"❌ Service error: {e}")
                    # Fallback to Sphinx
                    try:
                        text = self.recognizer.recognize_sphinx(audio)
                        return text if text else "[Speech not clear]", 0.5
                    except:
                        return "[Service unavailable]", 0.0
            
            # Cleanup
            if file_extension != 'wav' and wav_path != file_path:
                try:
                    os.unlink(wav_path)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"❌ File transcription failed: {e}", exc_info=True)
            return f"[Error: {str(e)}]", 0.0
    
    async def detect_language(self, audio_data: str, format: str = 'webm') -> str:
        """
        Detect language of audio
        
        Args:
            audio_data: Base64 encoded audio
            format: Audio format
        
        Returns:
            Detected language code (en-US, ar-EG, etc.)
        """
        # Try transcribing with different languages and compare confidence
        languages_to_try = ['en-US', 'ar-EG', 'ar-SA']
        best_language = 'en-US'
        best_confidence = 0.0
        
        for lang in languages_to_try:
            try:
                text = await self.transcribe(audio_data, format, lang)
                # Simple heuristic: longer transcription = better match
                confidence = len(text.split()) / 100.0
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_language = lang
            except:
                continue
        
        logger.info(f"🌐 Detected language: {best_language} (confidence: {best_confidence:.2f})")
        return best_language
    
    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages"""
        return [
            'en-US',  # English (US)
            'en-GB',  # English (UK)
            'ar-EG',  # Arabic (Egypt)
            'ar-SA',  # Arabic (Saudi Arabia)
            'ar-AE',  # Arabic (UAE)
            'fr-FR',  # French
            'de-DE',  # German
            'es-ES',  # Spanish
            'it-IT',  # Italian
        ]
