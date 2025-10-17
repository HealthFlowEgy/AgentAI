"""
RCM Data Models
Core database models for claims, eligibility, and workflow tracking
"""
from sqlalchemy import Column, String, Integer, DateTime, Numeric, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.services.database import Base


class ClaimRecord(Base):
    """Insurance claim records"""
    __tablename__ = "claims"
    
    claim_id = Column(String(50), primary_key=True)
    encounter_id = Column(String(50), nullable=False, index=True)
    patient_id = Column(String(50), nullable=False, index=True)
    insurance_company = Column(String(100))
    policy_number = Column(String(100))
    submission_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='submitted', index=True)
    hcx_reference = Column(String(100))
    total_charges = Column(Numeric(12, 2))
    expected_payment = Column(Numeric(12, 2))
    actual_payment = Column(Numeric(12, 2))
    denial_reason = Column(String(500))
    claim_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EligibilityCheck(Base):
    """Insurance eligibility check records"""
    __tablename__ = "eligibility_checks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(50), nullable=False, index=True)
    insurance_company = Column(String(100))
    policy_number = Column(String(100))
    check_date = Column(DateTime, default=datetime.utcnow, index=True)
    eligible = Column(Boolean)
    copay_amount = Column(Numeric(10, 2))
    deductible_remaining = Column(Numeric(10, 2))
    response_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowLog(Base):
    """Workflow execution logs"""
    __tablename__ = "workflow_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    encounter_id = Column(String(50), nullable=False, index=True)
    workflow_step = Column(String(100))
    agent_name = Column(String(100))
    status = Column(String(20))
    input_data = Column(JSON)
    output_data = Column(JSON)
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AuditLog(Base):
    """Audit trail for compliance"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(50))
    changes = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class WorkflowState(Base):
    """Workflow state for resumability"""
    __tablename__ = "workflow_state"
    
    workflow_id = Column(String(50), primary_key=True)
    encounter_id = Column(String(50), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False, default="end_to_end_rcm")
    current_step = Column(Integer, nullable=False, default=0)
    total_steps = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default='pending', index=True)
    step_results = Column(JSON, default=dict)
    workflow_metadata = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    error_step = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)


class PayerConfig(Base):
    """Payer-specific configuration"""
    __tablename__ = "payer_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    payer_code = Column(String(50), unique=True, nullable=False)
    payer_name = Column(String(200), nullable=False)
    hcx_participant_code = Column(String(100))
    requires_preauth = Column(Boolean, default=False)
    preauth_threshold = Column(Numeric(10, 2))
    config_data = Column(JSON)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserRole(Base):
    """User roles for RBAC"""
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), unique=True, nullable=False)
    permissions = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    """System users"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(200))
    role_id = Column(Integer, ForeignKey('user_roles.id'))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    role = relationship("UserRole")

