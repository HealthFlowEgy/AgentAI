"""
Medical Code Database Models
ICD-10, CPT, and Medical Necessity Rules
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime
from src.services.database import Base


class ICD10Code(Base):
    """ICD-10 Diagnosis Codes"""
    __tablename__ = "icd10_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(100))
    subcategory = Column(String(100))
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    billable = Column(Boolean, default=True)
    
    # Metadata
    chapter = Column(String(200))
    block = Column(String(200))
    
    # Search optimization
    __table_args__ = (
        Index('idx_icd10_description', 'description', postgresql_using='gin',
              postgresql_ops={'description': 'gin_trgm_ops'}),
        Index('idx_icd10_category', 'category'),
    )


class CPTCode(Base):
    """CPT Procedure Codes"""
    __tablename__ = "cpt_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(100))
    subcategory = Column(String(100))
    
    # Pricing
    base_rvu = Column(Float, nullable=True)  # Relative Value Unit
    facility_fee = Column(Float, nullable=True)
    non_facility_fee = Column(Float, nullable=True)
    
    # Modifiers
    common_modifiers = Column(ARRAY(String), default=list)
    
    # Metadata
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    
    # Search optimization
    __table_args__ = (
        Index('idx_cpt_description', 'description', postgresql_using='gin',
              postgresql_ops={'description': 'gin_trgm_ops'}),
        Index('idx_cpt_category', 'category'),
    )


class HCPCSCode(Base):
    """HCPCS Codes (Healthcare Common Procedure Coding System)"""
    __tablename__ = "hcpcs_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(100))
    subcategory = Column(String(100))
    
    # Metadata
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    
    # Search optimization
    __table_args__ = (
        Index('idx_hcpcs_description', 'description', postgresql_using='gin',
              postgresql_ops={'description': 'gin_trgm_ops'}),
        Index('idx_hcpcs_category', 'category'),
    )


class MedicalNecessityRule(Base):
    """Medical Necessity Rules - ICD-10 to CPT mapping"""
    __tablename__ = "medical_necessity_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Codes
    cpt_code = Column(String(10), nullable=False, index=True)
    icd10_codes = Column(ARRAY(String), nullable=False)  # List of valid ICD-10 codes
    
    # Rule details
    payer_id = Column(String(50), nullable=True, index=True)  # Null = applies to all payers
    rule_description = Column(Text)
    frequency_limit = Column(Integer, nullable=True)  # Max times per period
    frequency_period_days = Column(Integer, nullable=True)  # Period in days
    
    # Age/Gender restrictions
    min_age = Column(Integer, nullable=True)
    max_age = Column(Integer, nullable=True)
    gender_restriction = Column(String(1), nullable=True)  # M, F, or NULL
    
    # Metadata
    effective_date = Column(DateTime, default=datetime.utcnow)
    expiration_date = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_necessity_cpt', 'cpt_code'),
        Index('idx_necessity_payer', 'payer_id'),
        Index('idx_necessity_active', 'active'),
    )


class DenialCode(Base):
    """Insurance Denial Reason Codes"""
    __tablename__ = "denial_codes"
    
    code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(50))  # e.g., "medical_necessity", "coverage", "coding"
    
    # Resolution guidance
    typical_resolution = Column(Text)
    appeal_success_rate = Column(Float, default=0.0)
    avg_appeal_time_days = Column(Integer, default=30)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaymentCode(Base):
    """Payment Adjustment Reason Codes (CARC/RARC)"""
    __tablename__ = "payment_codes"
    
    code = Column(String(10), primary_key=True)
    code_type = Column(String(10), nullable=False)  # CARC or RARC
    description = Column(Text, nullable=False)
    category = Column(String(50))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

