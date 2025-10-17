"""
Authentication and Authorization System
Week 8 Implementation - JWT-based auth with RBAC
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import jwt

try:
    from passlib.context import CryptContext
    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False
    logging.warning("passlib not available, password hashing disabled")

from src.core.security_config import security_config, validate_password_strength

logger = logging.getLogger(__name__)


# Password hashing context
if PASSLIB_AVAILABLE:
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__rounds=12
    )
else:
    pwd_context = None


class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    BILLING_STAFF = "billing_staff"
    RECEPTIONIST = "receptionist"
    READONLY = "readonly"


class Permission(str, Enum):
    """System permissions"""
    # Patient permissions
    PATIENT_READ = "patient:read"
    PATIENT_WRITE = "patient:write"
    PATIENT_DELETE = "patient:delete"
    
    # Claim permissions
    CLAIM_READ = "claim:read"
    CLAIM_WRITE = "claim:write"
    CLAIM_SUBMIT = "claim:submit"
    CLAIM_APPROVE = "claim:approve"
    CLAIM_DELETE = "claim:delete"
    
    # Medical codes permissions
    CODE_READ = "code:read"
    CODE_WRITE = "code:write"
    
    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    
    # System admin
    SYSTEM_ADMIN = "system:admin"
    AUDIT_READ = "audit:read"


# Role-Permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.PATIENT_READ, Permission.PATIENT_WRITE, Permission.PATIENT_DELETE,
        Permission.CLAIM_READ, Permission.CLAIM_WRITE, Permission.CLAIM_SUBMIT,
        Permission.CLAIM_APPROVE, Permission.CLAIM_DELETE,
        Permission.CODE_READ, Permission.CODE_WRITE,
        Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE,
        Permission.SYSTEM_ADMIN, Permission.AUDIT_READ
    ],
    UserRole.DOCTOR: [
        Permission.PATIENT_READ, Permission.PATIENT_WRITE,
        Permission.CLAIM_READ, Permission.CLAIM_WRITE,
        Permission.CODE_READ
    ],
    UserRole.NURSE: [
        Permission.PATIENT_READ, Permission.PATIENT_WRITE,
        Permission.CLAIM_READ,
        Permission.CODE_READ
    ],
    UserRole.BILLING_STAFF: [
        Permission.PATIENT_READ,
        Permission.CLAIM_READ, Permission.CLAIM_WRITE, Permission.CLAIM_SUBMIT,
        Permission.CODE_READ
    ],
    UserRole.RECEPTIONIST: [
        Permission.PATIENT_READ, Permission.PATIENT_WRITE,
        Permission.CODE_READ
    ],
    UserRole.READONLY: [
        Permission.PATIENT_READ,
        Permission.CLAIM_READ,
        Permission.CODE_READ
    ]
}


class AuthService:
    """Authentication and authorization service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        if not pwd_context:
            raise RuntimeError("Password hashing not available (passlib not installed)")
        
        # Validate password strength
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValueError(error_msg)
        
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        if not pwd_context:
            raise RuntimeError("Password verification not available (passlib not installed)")
        
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(
        user_id: str,
        username: str,
        role: UserRole,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create JWT access token
        
        Args:
            user_id: User identifier
            username: Username
            role: User role
            additional_claims: Additional JWT claims
        
        Returns:
            JWT token string
        """
        if not security_config:
            raise RuntimeError("Security configuration not available")
        
        now = datetime.utcnow()
        expires = now + timedelta(minutes=security_config.jwt_access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "username": username,
            "role": role.value,
            "type": "access",
            "iat": now,
            "exp": expires,
            "iss": security_config.jwt_issuer,
            "aud": security_config.jwt_audience
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(
            payload,
            security_config.jwt_secret_key,
            algorithm=security_config.jwt_algorithm
        )
        
        logger.info(f"Access token created for user {username} (role: {role.value})")
        return token
    
    @staticmethod
    def create_refresh_token(user_id: str, username: str) -> str:
        """Create JWT refresh token"""
        if not security_config:
            raise RuntimeError("Security configuration not available")
        
        now = datetime.utcnow()
        expires = now + timedelta(days=security_config.jwt_refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "username": username,
            "type": "refresh",
            "iat": now,
            "exp": expires,
            "iss": security_config.jwt_issuer,
            "aud": security_config.jwt_audience
        }
        
        token = jwt.encode(
            payload,
            security_config.jwt_secret_key,
            algorithm=security_config.jwt_algorithm
        )
        
        return token
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        
        Raises:
            jwt.ExpiredSignatureError: Token expired
            jwt.InvalidTokenError: Invalid token
        """
        if not security_config:
            raise RuntimeError("Security configuration not available")
        
        try:
            payload = jwt.decode(
                token,
                security_config.jwt_secret_key,
                algorithms=[security_config.jwt_algorithm],
                issuer=security_config.jwt_issuer,
                audience=security_config.jwt_audience
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise
    
    @staticmethod
    def get_user_permissions(role: UserRole) -> List[Permission]:
        """Get permissions for a role"""
        return ROLE_PERMISSIONS.get(role, [])
    
    @staticmethod
    def has_permission(role: UserRole, required_permission: Permission) -> bool:
        """Check if role has required permission"""
        user_permissions = AuthService.get_user_permissions(role)
        
        # Admin has all permissions
        if Permission.SYSTEM_ADMIN in user_permissions:
            return True
        
        return required_permission in user_permissions
    
    @staticmethod
    def require_permission(role: UserRole, required_permission: Permission):
        """
        Require a specific permission (raises exception if not authorized)
        
        Args:
            role: User role
            required_permission: Required permission
        
        Raises:
            PermissionError: User does not have required permission
        """
        if not AuthService.has_permission(role, required_permission):
            raise PermissionError(
                f"Role {role.value} does not have permission {required_permission.value}"
            )


class TokenPayload:
    """JWT token payload"""
    
    def __init__(self, payload: Dict[str, Any]):
        self.user_id: str = payload.get("sub")
        self.username: str = payload.get("username")
        self.role: UserRole = UserRole(payload.get("role"))
        self.token_type: str = payload.get("type")
        self.issued_at: datetime = datetime.fromtimestamp(payload.get("iat"))
        self.expires_at: datetime = datetime.fromtimestamp(payload.get("exp"))
        self.issuer: str = payload.get("iss")
        self.audience: str = payload.get("aud")
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_access_token(self) -> bool:
        """Check if this is an access token"""
        return self.token_type == "access"
    
    def is_refresh_token(self) -> bool:
        """Check if this is a refresh token"""
        return self.token_type == "refresh"
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has permission"""
        return AuthService.has_permission(self.role, permission)


def authenticate_user(username: str, password: str, user_db: Dict[str, Dict]) -> Optional[Dict[str, Any]]:
    """
    Authenticate user with username and password
    
    Args:
        username: Username
        password: Plain password
        user_db: User database (dict)
    
    Returns:
        User dict if authenticated, None otherwise
    """
    user = user_db.get(username)
    if not user:
        logger.warning(f"Authentication failed: user {username} not found")
        return None
    
    if not AuthService.verify_password(password, user["password_hash"]):
        logger.warning(f"Authentication failed: invalid password for user {username}")
        return None
    
    logger.info(f"User {username} authenticated successfully")
    return user


def create_user(
    username: str,
    password: str,
    role: UserRole,
    email: Optional[str] = None,
    full_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new user
    
    Args:
        username: Username
        password: Plain password
        role: User role
        email: Email address
        full_name: Full name
    
    Returns:
        User dict
    """
    password_hash = AuthService.hash_password(password)
    
    user = {
        "username": username,
        "password_hash": password_hash,
        "role": role.value,
        "email": email,
        "full_name": full_name,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True,
        "failed_login_attempts": 0
    }
    
    logger.info(f"User {username} created with role {role.value}")
    return user

