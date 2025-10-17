"""
HCX (Health Claims Exchange) Configuration
Week 5-6 Implementation
"""
from pydantic import BaseSettings, Field, validator
from typing import Optional
import os


class HCXConfig(BaseSettings):
    """HCX configuration settings for Egyptian HCX platform"""
    
    # Environment
    environment: str = Field(
        default="staging",
        description="HCX environment: staging or production"
    )
    
    # Base URLs (Egyptian HCX Platform)
    staging_base_url: str = "https://staging-hcx.swasth.app/api/v1"
    production_base_url: str = "https://hcx.swasth.app/api/v1"
    
    # Authentication
    participant_code: str = Field(
        ...,
        description="HCX participant code (hospital identifier)"
    )
    
    username: str = Field(
        ...,
        description="HCX username"
    )
    
    password: str = Field(
        ...,
        description="HCX password"
    )
    
    # Encryption keys (PEM format, base64 encoded)
    encryption_private_key: str = Field(
        ...,
        description="Private key for request encryption (PEM format, base64)"
    )
    
    encryption_public_key: str = Field(
        ...,
        description="Public key for response decryption (PEM format, base64)"
    )
    
    # API Keys
    api_key: Optional[str] = Field(
        None,
        description="HCX API key if required"
    )
    
    # Timeouts
    request_timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed requests"
    )
    
    retry_delay: int = Field(
        default=2,
        description="Initial delay between retries in seconds (exponential backoff)"
    )
    
    # Rate limiting
    rate_limit_per_minute: int = Field(
        default=60,
        description="Maximum requests per minute to avoid throttling"
    )
    
    # Webhook configuration
    webhook_url: Optional[str] = Field(
        None,
        description="Webhook URL for async responses"
    )
    
    @property
    def base_url(self) -> str:
        """Get base URL based on environment"""
        if self.environment == "production":
            return self.production_base_url
        return self.staging_base_url
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment value"""
        if v not in ['staging', 'production']:
            raise ValueError('environment must be staging or production')
        return v
    
    @validator('participant_code')
    def validate_participant_code(cls, v):
        """Validate participant code format"""
        if not v or len(v) < 5:
            raise ValueError('participant_code must be at least 5 characters')
        return v
    
    @validator('max_retries')
    def validate_max_retries(cls, v):
        """Validate max retries"""
        if v < 0 or v > 10:
            raise ValueError('max_retries must be between 0 and 10')
        return v
    
    class Config:
        env_prefix = "HCX_"
        case_sensitive = False
        env_file = ".env"


# Global instance - will be initialized when module is imported
try:
    hcx_config = HCXConfig()
except Exception as e:
    import logging
    logging.warning(f"HCX configuration not loaded: {e}")
    hcx_config = None

