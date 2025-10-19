"""
Insurance coverage data model
"""
from sqlalchemy import Column, String, Integer, DateTime, Date, Numeric, Boolean, JSON, ForeignKey
from datetime import datetime
from src.services.database import Base


class Coverage(Base):
    """Insurance coverage information"""
    __tablename__ = "coverage"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False, index=True)
    insurance_company = Column(String(100), nullable=False)
    policy_number = Column(String(100), nullable=False)
    group_number = Column(String(100))
    plan_name = Column(String(200))
    coverage_type = Column(String(50))  # primary, secondary, etc.
    effective_date = Column(Date)
    termination_date = Column(Date)
    copay = Column(Numeric(10, 2))
    deductible = Column(Numeric(10, 2))
    deductible_met = Column(Numeric(10, 2))
    out_of_pocket_max = Column(Numeric(10, 2))
    out_of_pocket_met = Column(Numeric(10, 2))
    coverage_details = Column(JSON)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

