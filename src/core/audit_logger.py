"""
Comprehensive Audit Logging System
Week 8 Implementation - HIPAA-compliant audit trail
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import uuid


logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Audit event types (HIPAA compliance)"""
    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGE = "auth.password.change"
    PASSWORD_RESET = "auth.password.reset"
    
    # Authorization events
    ACCESS_GRANTED = "authz.access.granted"
    ACCESS_DENIED = "authz.access.denied"
    PERMISSION_CHANGE = "authz.permission.change"
    
    # PHI Access (Protected Health Information)
    PHI_READ = "phi.read"
    PHI_WRITE = "phi.write"
    PHI_DELETE = "phi.delete"
    PHI_EXPORT = "phi.export"
    
    # Patient data
    PATIENT_CREATE = "patient.create"
    PATIENT_READ = "patient.read"
    PATIENT_UPDATE = "patient.update"
    PATIENT_DELETE = "patient.delete"
    
    # Claim operations
    CLAIM_CREATE = "claim.create"
    CLAIM_READ = "claim.read"
    CLAIM_UPDATE = "claim.update"
    CLAIM_SUBMIT = "claim.submit"
    CLAIM_APPROVE = "claim.approve"
    CLAIM_DENY = "claim.deny"
    CLAIM_DELETE = "claim.delete"
    
    # Medical codes
    CODE_READ = "code.read"
    CODE_WRITE = "code.write"
    
    # System events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"
    SYSTEM_CONFIG_CHANGE = "system.config.change"
    
    # Security events
    SECURITY_BREACH_ATTEMPT = "security.breach.attempt"
    RATE_LIMIT_EXCEEDED = "security.rate_limit.exceeded"
    INVALID_TOKEN = "security.invalid_token"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"


class AuditSeverity(str, Enum):
    """Audit event severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogger:
    """
    HIPAA-compliant audit logging system
    
    Requirements:
    - Log all PHI access
    - Log all authentication/authorization events
    - Log all data modifications
    - Tamper-proof logging
    - 7-year retention
    """
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or "logs/audit.log"
        self.logger = logging.getLogger("audit")
        
        # Configure audit logger
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        result: str = "success",
        severity: AuditSeverity = AuditSeverity.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """
        Log an audit event
        
        Args:
            event_type: Type of event
            user_id: User identifier
            username: Username
            resource_type: Type of resource accessed
            resource_id: Resource identifier
            action: Action performed
            result: Result (success/failure)
            severity: Event severity
            ip_address: Client IP address
            user_agent: Client user agent
            additional_data: Additional event data
            error_message: Error message if applicable
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type.value,
            "severity": severity.value,
            "user_id": user_id,
            "username": username,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "result": result,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "error_message": error_message,
            "additional_data": additional_data or {}
        }
        
        # Log to file (JSON format for easy parsing)
        self.logger.info(json.dumps(event))
        
        # Also log to standard logger for monitoring
        log_msg = (
            f"[AUDIT] {event_type.value} | "
            f"User: {username or 'anonymous'} | "
            f"Resource: {resource_type}/{resource_id} | "
            f"Result: {result}"
        )
        
        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == AuditSeverity.ERROR:
            logger.error(log_msg)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
    
    # Convenience methods for common events
    
    def log_login(self, username: str, success: bool, ip_address: Optional[str] = None):
        """Log login attempt"""
        self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE,
            username=username,
            result="success" if success else "failure",
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            ip_address=ip_address
        )
    
    def log_logout(self, user_id: str, username: str):
        """Log logout"""
        self.log_event(
            event_type=AuditEventType.LOGOUT,
            user_id=user_id,
            username=username,
            result="success",
            severity=AuditSeverity.INFO
        )
    
    def log_phi_access(
        self,
        user_id: str,
        username: str,
        patient_id: str,
        action: str,
        ip_address: Optional[str] = None
    ):
        """Log PHI (Protected Health Information) access"""
        event_type = {
            "read": AuditEventType.PHI_READ,
            "write": AuditEventType.PHI_WRITE,
            "delete": AuditEventType.PHI_DELETE,
            "export": AuditEventType.PHI_EXPORT
        }.get(action.lower(), AuditEventType.PHI_READ)
        
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            username=username,
            resource_type="patient",
            resource_id=patient_id,
            action=action,
            result="success",
            severity=AuditSeverity.INFO,
            ip_address=ip_address,
            additional_data={"phi_access": True}
        )
    
    def log_access_denied(
        self,
        user_id: str,
        username: str,
        resource_type: str,
        resource_id: str,
        required_permission: str,
        ip_address: Optional[str] = None
    ):
        """Log access denied"""
        self.log_event(
            event_type=AuditEventType.ACCESS_DENIED,
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            action="access",
            result="denied",
            severity=AuditSeverity.WARNING,
            ip_address=ip_address,
            additional_data={"required_permission": required_permission}
        )
    
    def log_claim_operation(
        self,
        user_id: str,
        username: str,
        claim_id: str,
        operation: str,
        result: str = "success",
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log claim operation"""
        event_type_map = {
            "create": AuditEventType.CLAIM_CREATE,
            "read": AuditEventType.CLAIM_READ,
            "update": AuditEventType.CLAIM_UPDATE,
            "submit": AuditEventType.CLAIM_SUBMIT,
            "approve": AuditEventType.CLAIM_APPROVE,
            "deny": AuditEventType.CLAIM_DENY,
            "delete": AuditEventType.CLAIM_DELETE
        }
        
        event_type = event_type_map.get(operation.lower(), AuditEventType.CLAIM_READ)
        
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            username=username,
            resource_type="claim",
            resource_id=claim_id,
            action=operation,
            result=result,
            severity=AuditSeverity.INFO,
            additional_data=additional_data
        )
    
    def log_security_event(
        self,
        event_type: AuditEventType,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        description: str = "",
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log security event"""
        self.log_event(
            event_type=event_type,
            username=username,
            result="detected",
            severity=AuditSeverity.CRITICAL,
            ip_address=ip_address,
            error_message=description,
            additional_data=additional_data
        )
    
    def log_system_event(
        self,
        event_type: AuditEventType,
        description: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log system event"""
        self.log_event(
            event_type=event_type,
            result="success",
            severity=severity,
            error_message=description,
            additional_data=additional_data
        )


# Global audit logger instance
audit_logger = AuditLogger()


# Decorator for audit logging
def audit_log(event_type: AuditEventType, resource_type: Optional[str] = None):
    """
    Decorator to automatically log function calls
    
    Usage:
        @audit_log(AuditEventType.PATIENT_READ, resource_type="patient")
        async def get_patient(patient_id: str, user: User):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user info from kwargs
            user = kwargs.get('user') or kwargs.get('current_user')
            user_id = user.id if user and hasattr(user, 'id') else None
            username = user.username if user and hasattr(user, 'username') else None
            
            # Extract resource ID
            resource_id = kwargs.get('patient_id') or kwargs.get('claim_id') or kwargs.get('id')
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful operation
                audit_logger.log_event(
                    event_type=event_type,
                    user_id=user_id,
                    username=username,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=func.__name__,
                    result="success",
                    severity=AuditSeverity.INFO
                )
                
                return result
                
            except Exception as e:
                # Log failed operation
                audit_logger.log_event(
                    event_type=event_type,
                    user_id=user_id,
                    username=username,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=func.__name__,
                    result="failure",
                    severity=AuditSeverity.ERROR,
                    error_message=str(e)
                )
                raise
        
        return wrapper
    return decorator

