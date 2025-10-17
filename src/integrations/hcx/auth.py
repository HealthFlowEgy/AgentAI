"""
HCX Authentication and Encryption Management
Week 5-6 Implementation
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
import base64
import json

try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from .config import hcx_config

logger = logging.getLogger(__name__)


class HCXAuthManager:
    """Manage HCX authentication, tokens, and encryption"""
    
    def __init__(self):
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.refresh_token: Optional[str] = None
        self._lock = asyncio.Lock()
        self.private_key = None
        self.public_key = None
        
        # Load encryption keys if available
        if CRYPTO_AVAILABLE and hcx_config:
            self._load_encryption_keys()
    
    def _load_encryption_keys(self):
        """Load and parse encryption keys from configuration"""
        try:
            # Decode base64 encoded keys
            private_key_pem = base64.b64decode(hcx_config.encryption_private_key)
            public_key_pem = base64.b64decode(hcx_config.encryption_public_key)
            
            # Load private key for signing/decryption
            self.private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=None,
                backend=default_backend()
            )
            
            # Load public key for verification/encryption
            self.public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=default_backend()
            )
            
            logger.info("✅ HCX encryption keys loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load encryption keys: {e}")
            raise ValueError(f"Invalid encryption keys: {e}")
    
    async def get_access_token(self) -> str:
        """
        Get valid access token, refreshing if necessary
        Thread-safe with automatic refresh
        """
        if not hcx_config:
            raise ValueError("HCX configuration not available")
        
        async with self._lock:
            # Check if token is valid (with 5-minute buffer)
            if self.access_token and self.token_expires_at:
                if datetime.utcnow() < self.token_expires_at - timedelta(minutes=5):
                    return self.access_token
            
            # Token expired or missing, get new token
            await self._authenticate()
            return self.access_token
    
    async def _authenticate(self):
        """Authenticate with HCX and get access token"""
        url = f"{hcx_config.base_url}/auth/token"
        
        payload = {
            "participantCode": hcx_config.participant_code,
            "username": hcx_config.username,
            "password": hcx_config.password
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        if hcx_config.api_key:
            headers["X-API-Key"] = hcx_config.api_key
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=hcx_config.request_timeout
                )
                
                response.raise_for_status()
                data = response.json()
                
                self.access_token = data['access_token']
                self.refresh_token = data.get('refresh_token')
                
                # Token typically valid for 1 hour
                expires_in = data.get('expires_in', 3600)
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                logger.info(f"✅ HCX authentication successful, token expires at {self.token_expires_at}")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HCX authentication failed: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"HCX authentication failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"❌ HCX authentication error: {e}")
            raise
    
    def encrypt_payload(self, payload: Dict[str, Any]) -> str:
        """
        Encrypt request payload using public key
        Returns base64 encoded encrypted data
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available, returning unencrypted payload")
            return base64.b64encode(json.dumps(payload).encode()).decode()
        
        if not self.public_key:
            raise ValueError("Public key not loaded")
        
        try:
            # Convert payload to JSON bytes
            payload_bytes = json.dumps(payload).encode('utf-8')
            
            # Encrypt using public key
            encrypted = self.public_key.encrypt(
                payload_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Return base64 encoded
            return base64.b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ Payload encryption failed: {e}")
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt_response(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt response data using private key
        Accepts base64 encoded encrypted data
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available, attempting to decode as base64 JSON")
            try:
                return json.loads(base64.b64decode(encrypted_data))
            except:
                return {"error": "Unable to decrypt response"}
        
        if not self.private_key:
            raise ValueError("Private key not loaded")
        
        try:
            # Decode base64
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # Decrypt using private key
            decrypted = self.private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Parse JSON
            return json.loads(decrypted.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"❌ Response decryption failed: {e}")
            raise ValueError(f"Decryption failed: {e}")
    
    async def refresh_access_token(self) -> str:
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            # No refresh token, do full authentication
            await self._authenticate()
            return self.access_token
        
        url = f"{hcx_config.base_url}/auth/refresh"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.refresh_token}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    timeout=hcx_config.request_timeout
                )
                
                response.raise_for_status()
                data = response.json()
                
                self.access_token = data['access_token']
                expires_in = data.get('expires_in', 3600)
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                logger.info("✅ HCX token refreshed successfully")
                return self.access_token
                
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}, falling back to full authentication")
            await self._authenticate()
            return self.access_token
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        if not self.access_token:
            raise ValueError("No access token available, call get_access_token() first")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-HCX-Participant-Code": hcx_config.participant_code
        }
        
        if hcx_config.api_key:
            headers["X-API-Key"] = hcx_config.api_key
        
        return headers


# Global instance
auth_manager = HCXAuthManager() if hcx_config else None

