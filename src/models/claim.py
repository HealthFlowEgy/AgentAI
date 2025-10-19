"""
Claim data models
"""
from sqlalchemy import Column, String, Integer, DateTime, Numeric, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.services.database import Base


class Claim(Base):
    """Insurance claim"""
    __tablename__ = "claims"
    
    claim_id = Column(String(50), primary_key=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False, index=True)
    encounter_id = Column(String(50), nullable=False, index=True)
    insurance_company = Column(String(100))
    policy_number = Column(String(100))
    submission_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='draft', index=True)
    hcx_reference = Column(String(100))
    total_charges = Column(Numeric(12, 2))
    expected_payment = Column(Numeric(12, 2))
    actual_payment = Column(Numeric(12, 2))
    denial_reason = Column(Text)
    claim_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClaimItem(Base):
    """Claim line item"""
    __tablename__ = "claim_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String(50), ForeignKey('claims.claim_id'), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    cpt_code = Column(String(10), nullable=False)
    description = Column(Text)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2))
    total_price = Column(Numeric(10, 2))
    modifiers = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClaimDiagnosis(Base):
    """Claim diagnosis"""
    __tablename__ = "claim_diagnoses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String(50), ForeignKey('claims.claim_id'), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    icd10_code = Column(String(10), nullable=False)
    description = Column(Text)
    type = Column(String(20))  # principal, secondary, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

