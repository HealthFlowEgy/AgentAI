"""
Patient data model
"""
from sqlalchemy import Column, String, Integer, DateTime, Date, Boolean, JSON
from datetime import datetime
from src.services.database import Base


class Patient(Base):
    """Patient information"""
    __tablename__ = "patients"
    
    patient_id = Column(String(50), primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10))
    phone = Column(String(20))
    email = Column(String(200))
    address = Column(JSON)
    insurance_info = Column(JSON)
    medical_history = Column(JSON)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

