"""
Secure Configuration Management with Environment Variable Validation
Fixes: Hardcoded secrets vulnerability (Critical)
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with mandatory security validation"""
    
    # Application
    APP_NAME: str = "Healthcare RCM System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # Security - NO DEFAULTS, REQUIRED via environment
    JWT_SECRET: str = Field(..., min_length=32, description="JWT signing secret")
    ENCRYPTION_KEY: str = Field(..., min_length=32, description="Data encryption key")
    
    # HCX Platform
    HCX_API_URL: str = Field(..., description="HCX API base URL")
    HCX_GATEWAY_URL: str = Field(..., description="HCX Gateway URL")
    HCX_USERNAME: str = Field(..., description="HCX username")
    HCX_PASSWORD: str = Field(..., description="HCX password")
    HCX_REQUEST_TIMEOUT: int = Field(default=30, description="HCX request timeout in seconds")
    HCX_CONNECT_TIMEOUT: int = Field(default=10, description="HCX connect timeout in seconds")
    
    # Database Configuration
    DB_HOST: str = Field(default="localhost", env="DB_HOST")
    DB_PORT: int = Field(default=5432, env="DB_PORT")
    DB_NAME: str = Field(default="healthcare_rcm", env="DB_NAME")
    DB_USER: str = Field(default="rcm_user", env="DB_USER")
    DB_PASSWORD: str = Field(..., description="Database password")
    
    # Database Connection Pooling
    DB_POOL_SIZE: int = Field(default=20, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Max connections beyond pool size")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Pool timeout in seconds")
    DB_POOL_RECYCLE: int = Field(default=3600, description="Recycle connections after seconds")
    DB_ECHO: bool = Field(default=False, description="Echo SQL queries")
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_SSL: bool = Field(default=False, env="REDIS_SSL")
    
    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    KAFKA_CLAIMS_TOPIC: str = Field(default="rcm.claims", env="KAFKA_CLAIMS_TOPIC")
    KAFKA_ENABLE: bool = Field(default=False, env="KAFKA_ENABLE")
    
    # OpenAI/LLM Configuration
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4", env="OPENAI_MODEL")
    OPENAI_TEMPERATURE: float = Field(default=0.1, env="OPENAI_TEMPERATURE")
    OPENAI_MAX_TOKENS: int = Field(default=2000, env="OPENAI_MAX_TOKENS")
    
    # Retry Configuration
    MAX_RETRIES: int = Field(default=3, description="Max retry attempts")
    RETRY_BACKOFF_FACTOR: float = Field(default=2.0, description="Exponential backoff multiplier")
    RETRY_MAX_WAIT: int = Field(default=10, description="Max wait between retries (seconds)")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="API rate limit per minute")
    RATE_LIMIT_BURST: int = Field(default=10, description="Rate limit burst allowance")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")  # json or text
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # CORS Configuration
    CORS_ORIGINS: list = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True)
    
    # Feature Flags
    ENABLE_ELIGIBILITY_CHECK: bool = Field(default=True, env="ENABLE_ELIGIBILITY_CHECK")
    ENABLE_PREAUTH: bool = Field(default=True, env="ENABLE_PREAUTH")
    ENABLE_CLAIM_SUBMISSION: bool = Field(default=True, env="ENABLE_CLAIM_SUBMISSION")
    ENABLE_ANALYTICS: bool = Field(default=True, env="ENABLE_ANALYTICS")
    
    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('ENVIRONMENT', 'development')}",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )
    
    @field_validator('JWT_SECRET', 'ENCRYPTION_KEY')
    @classmethod
    def validate_production_secrets(cls, v: str, info) -> str:
        """Ensure secrets are properly configured for production"""
        field_name = info.field_name
        
        # Check for placeholder values
        dangerous_patterns = ['your-', 'change-me', 'example', 'test', 'demo']
        if any(pattern in v.lower() for pattern in dangerous_patterns):
            raise ValueError(
                f"{field_name} contains placeholder value. "
                f"Set proper secret via environment variable."
            )
        
        # Minimum length check
        if len(v) < 32:
            raise ValueError(
                f"{field_name} must be at least 32 characters long. "
                f"Generate with: openssl rand -hex 32"
            )
        
        return v
    
    @field_validator('ENVIRONMENT')
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed = ['development', 'staging', 'production', 'test']
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of: {allowed}")
        return v
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        allowed = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v = v.upper()
        if v not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return v
    
    @property
    def database_url(self) -> str:
        """Construct database URL"""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        protocol = "rediss" if self.REDIS_SSL else "redis"
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"{protocol}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == "development"
    
    def validate_production_readiness(self) -> list[str]:
        """
        Validate production readiness and return list of issues
        Should be called at application startup
        """
        issues = []
        
        if self.is_production:
            # Production-specific checks
            if self.DEBUG:
                issues.append("DEBUG mode enabled in production")
            
            if "localhost" in self.HCX_API_URL:
                issues.append("HCX_API_URL points to localhost in production")
            
            if "localhost" in self.DB_HOST:
                issues.append("Database on localhost in production")
            
            if not self.REDIS_SSL and self.REDIS_HOST != "localhost":
                issues.append("Redis SSL disabled for remote connection")
            
            if self.LOG_LEVEL == "DEBUG":
                issues.append("DEBUG logging in production")
        
        return issues


# Singleton instance
settings = Settings()

# Validate on import
if settings.is_production:
    issues = settings.validate_production_readiness()
    if issues:
        raise RuntimeError(
            f"Production readiness check failed:\n" + 
            "\n".join(f"  - {issue}" for issue in issues)
        )

