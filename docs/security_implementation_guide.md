# Security Implementation Guide

**Objective:** Fix critical security vulnerabilities by removing hardcoded secrets and implementing production-ready configuration management.

---

## 1. Create `.env.example` File

First, create a `.env.example` file in the project root to guide developers on required environment variables. **Do not** commit the actual `.env` file to version control.

```
# .env.example

# Application Settings
APP_NAME="Healthcare RCM System"
DEBUG=False

# HCX Platform
HCX_API_URL="http://localhost:8080"
HCX_GATEWAY_URL="http://localhost:8090"
HCX_USERNAME="hospital_user"
HCX_PASSWORD="secure_password"

# Database
DB_HOST="localhost"
DB_PORT=5432
DB_NAME="healthcare_rcm"
DB_USER="rcm_user"
DB_PASSWORD="rcm_password"

# Redis Cache
REDIS_HOST="localhost"
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS="localhost:9092"

# OpenAI/LLM
OPENAI_API_KEY="your-openai-api-key"

# --- PRODUCTION SECRETS (DO NOT USE DEFAULTS) ---
# Generate with: openssl rand -hex 32
JWT_SECRET=""
ENCRYPTION_KEY=""
```

## 2. Update `config/settings.py`

Modify the `settings.py` file to enforce that production secrets are loaded from environment variables and are never hardcoded. This change will cause the application to fail on startup if secrets are not properly configured, preventing accidental deployment of insecure defaults.

```python
# config/settings.py

from pydantic import Field, validator
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings with production-grade security"""
    
    # Application
    APP_NAME: str = "Healthcare RCM System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # HCX Platform
    HCX_API_URL: str = "http://localhost:8080"
    HCX_GATEWAY_URL: str = "http://localhost:8090"
    HCX_USERNAME: str = "hospital_user"
    HCX_PASSWORD: str = "secure_password"
    
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "healthcare_rcm"
    DB_USER: str = "rcm_user"
    DB_PASSWORD: str = "rcm_password"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # Redis Cache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    
    # OpenAI/LLM
    OPENAI_API_KEY: str
    
    # --- PRODUCTION SECRETS --- #
    # These have no default values and must be set in the environment.
    JWT_SECRET: str = Field(..., min_length=32)
    ENCRYPTION_KEY: str = Field(..., min_length=32)

    @validator("JWT_SECRET", "ENCRYPTION_KEY")
    def validate_production_secrets(cls, v, field):
        if v.startswith("your-") or len(v) < 32:
            raise ValueError(f"{field.name} must be a unique, 32-character minimum string and not a default value.")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

```

### Key Changes:

- **`JWT_SECRET` and `ENCRYPTION_KEY`** are now defined with `Field(..., min_length=32)`, which makes them **required** and enforces a minimum length. The `...` indicates there is no default value.
- The **`validate_production_secrets`** validator prevents the application from starting if the secrets look like default placeholder values.
- Database connection pooling settings (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) have been added for production readiness.

## 3. How to Apply This Fix

1.  **Create the `.env.example` file** in your project root.
2.  **Replace the content** of `config/settings.py` with the code above.
3.  **Create a `.env` file** (and add it to `.gitignore`) with your actual production secrets.
4.  **Run the application.** It will now fail to start if the secrets are not securely configured.

