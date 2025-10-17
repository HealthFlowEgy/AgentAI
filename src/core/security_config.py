"""
Security Configuration and Hardening
Week 8 Implementation - Production-grade security settings
"""
from pydantic import BaseSettings, Field, validator
from typing import List, Optional
import secrets
import os


class SecurityConfig(BaseSettings):
    """
    Comprehensive security configuration
    Implements OWASP best practices and HIPAA compliance requirements
    """
    
    # ========================================
    # JWT Settings
    # ========================================
    jwt_secret_key: str = Field(
        ...,
        description="JWT secret key - MUST be set in production (min 32 chars)"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "healthcare-rcm-system"
    jwt_audience: str = "healthcare-rcm-api"
    
    # ========================================
    # Password Requirements (HIPAA compliant)
    # ========================================
    password_min_length: int = 12
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special: bool = True
    password_max_age_days: int = 90
    password_history_count: int = 5  # Prevent reuse of last 5 passwords
    max_login_attempts: int = 5
    account_lockout_duration_minutes: int = 30
    
    # ========================================
    # Rate Limiting (DDoS Protection)
    # ========================================
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    rate_limit_per_day: int = 10000
    rate_limit_burst: int = 10
    
    # ========================================
    # CORS Configuration
    # ========================================
    cors_enabled: bool = True
    cors_allowed_origins: List[str] = Field(
        default=["https://yourdomain.com"],
        description="Allowed CORS origins (no wildcards in production)"
    )
    cors_allow_credentials: bool = True
    cors_allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    cors_allowed_headers: List[str] = ["Content-Type", "Authorization", "X-API-Key"]
    cors_max_age: int = 600
    
    # ========================================
    # Session Management
    # ========================================
    session_timeout_minutes: int = 30
    session_absolute_timeout_hours: int = 8
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "strict"
    
    # ========================================
    # API Security
    # ========================================
    api_key_header: str = "X-API-Key"
    require_https: bool = True
    min_tls_version: str = "1.2"
    
    # ========================================
    # Encryption
    # ========================================
    encryption_algorithm: str = "AES-256-GCM"
    data_at_rest_encryption: bool = True
    phi_encryption_required: bool = True  # Protected Health Information
    
    # ========================================
    # Audit Logging (HIPAA Requirement)
    # ========================================
    audit_log_enabled: bool = True
    audit_log_retention_days: int = 2555  # 7 years for HIPAA
    audit_log_encryption: bool = True
    audit_log_phi_access: bool = True
    audit_log_authentication: bool = True
    audit_log_authorization: bool = True
    
    # ========================================
    # IP Filtering (Optional)
    # ========================================
    ip_whitelist_enabled: bool = False
    ip_whitelist: List[str] = []
    ip_blacklist_enabled: bool = True
    ip_blacklist: List[str] = []
    
    # ========================================
    # Security Headers
    # ========================================
    enable_hsts: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    
    enable_csp: bool = True
    csp_policy: str = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    
    enable_x_frame_options: bool = True
    x_frame_options: str = "DENY"
    
    enable_x_content_type_options: bool = True
    enable_x_xss_protection: bool = True
    
    # ========================================
    # Input Validation
    # ========================================
    max_request_size_mb: int = 10
    max_json_depth: int = 10
    sanitize_input: bool = True
    
    # ========================================
    # Compliance
    # ========================================
    hipaa_compliance_mode: bool = True
    gdpr_compliance_mode: bool = False
    
    # ========================================
    # Validators
    # ========================================
    
    @validator('jwt_secret_key')
    def validate_jwt_secret(cls, v):
        """Ensure JWT secret is secure"""
        if not v or v == "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32":
            raise ValueError(
                'JWT secret must be set in production. '
                'Generate with: openssl rand -hex 32'
            )
        if len(v) < 32:
            raise ValueError('JWT secret must be at least 32 characters')
        return v
    
    @validator('cors_allowed_origins')
    def validate_cors_origins(cls, v):
        """Validate CORS origins - no wildcards in production"""
        if '*' in v:
            raise ValueError(
                'Wildcard CORS origin (*) not allowed in production. '
                'Specify exact origins.'
            )
        for origin in v:
            if not origin.startswith(('http://', 'https://')):
                raise ValueError(f'Invalid CORS origin format: {origin}')
        return v
    
    @validator('password_min_length')
    def validate_password_length(cls, v):
        """Ensure password length meets security standards"""
        if v < 12:
            raise ValueError('Password minimum length must be at least 12 characters')
        return v
    
    @validator('rate_limit_per_minute')
    def validate_rate_limit(cls, v):
        """Ensure rate limiting is reasonable"""
        if v < 10 or v > 1000:
            raise ValueError('Rate limit per minute must be between 10 and 1000')
        return v
    
    @validator('audit_log_retention_days')
    def validate_audit_retention(cls, v, values):
        """Ensure HIPAA compliance for audit log retention"""
        if values.get('hipaa_compliance_mode') and v < 2555:  # 7 years
            raise ValueError('HIPAA requires 7 years (2555 days) of audit log retention')
        return v
    
    class Config:
        env_prefix = "SECURITY_"
        case_sensitive = False
        env_file = ".env"


# Global instance
try:
    security_config = SecurityConfig()
except Exception as e:
    import logging
    logging.warning(f"Security configuration not loaded: {e}")
    security_config = None


def get_security_headers() -> dict:
    """
    Get security headers for HTTP responses
    Implements OWASP security header best practices
    """
    if not security_config:
        return {}
    
    headers = {}
    
    # HSTS (HTTP Strict Transport Security)
    if security_config.enable_hsts:
        hsts_value = f"max-age={security_config.hsts_max_age}"
        if security_config.hsts_include_subdomains:
            hsts_value += "; includeSubDomains"
        if security_config.hsts_preload:
            hsts_value += "; preload"
        headers["Strict-Transport-Security"] = hsts_value
    
    # CSP (Content Security Policy)
    if security_config.enable_csp:
        headers["Content-Security-Policy"] = security_config.csp_policy
    
    # X-Frame-Options
    if security_config.enable_x_frame_options:
        headers["X-Frame-Options"] = security_config.x_frame_options
    
    # X-Content-Type-Options
    if security_config.enable_x_content_type_options:
        headers["X-Content-Type-Options"] = "nosniff"
    
    # X-XSS-Protection
    if security_config.enable_x_xss_protection:
        headers["X-XSS-Protection"] = "1; mode=block"
    
    # Referrer-Policy
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions-Policy
    headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return headers


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password against security requirements
    
    Args:
        password: Password to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not security_config:
        return True, ""
    
    if len(password) < security_config.password_min_length:
        return False, f"Password must be at least {security_config.password_min_length} characters"
    
    if security_config.password_require_uppercase and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if security_config.password_require_lowercase and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if security_config.password_require_numbers and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    if security_config.password_require_special:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            return False, "Password must contain at least one special character"
    
    return True, ""

