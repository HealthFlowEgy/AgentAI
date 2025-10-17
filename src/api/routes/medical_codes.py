"""
API endpoints for medical codes validation and search
Week 1-2 Implementation
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.medical_codes_service import MedicalCodesService

router = APIRouter(prefix="/api/v1/medical-codes", tags=["medical-codes"])


# Response Models
class ICD10ValidationResponse(BaseModel):
    valid: bool
    code: str
    description: Optional[str] = None
    billable: Optional[bool] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    error: Optional[str] = None


class CPTValidationResponse(BaseModel):
    valid: bool
    code: str
    description: Optional[str] = None
    category: Optional[str] = None
    modifier_allowed: Optional[bool] = None
    base_rate: Optional[float] = None
    rvu: Optional[float] = None
    error: Optional[str] = None


class CodeSearchResult(BaseModel):
    code: str
    description: str
    category: Optional[str] = None
    relevance: float


class MedicalNecessityRequest(BaseModel):
    cpt_code: str = Field(..., description="CPT procedure code")
    icd10_codes: List[str] = Field(..., description="List of diagnosis codes")
    insurance_type: Optional[str] = Field(None, description="Insurance type (e.g., Medicare, Allianz)")
    patient_age: Optional[int] = Field(None, ge=0, le=150, description="Patient age")
    patient_gender: Optional[str] = Field(None, description="Patient gender (M/F/O)")


class MedicalNecessityResponse(BaseModel):
    approved: bool
    reason: str
    prior_auth_required: bool
    confidence: str
    matched_rules: List[dict] = []
    suggestion: Optional[str] = None


class CodeStatistics(BaseModel):
    icd10_codes: int
    cpt_codes: int
    hcpcs_codes: int
    medical_necessity_rules: int
    total_codes: int
    last_updated: str


# Dependency to get database session
async def get_db_session():
    """
    Placeholder for database session dependency
    In production, this should return an actual AsyncSession
    """
    # This will be replaced with actual database session from dependency injection
    raise HTTPException(status_code=501, detail="Database session not configured")


# API Endpoints
@router.get("/icd10/{code}/validate", response_model=ICD10ValidationResponse)
async def validate_icd10_code(
    code: str,
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Validate an ICD-10 diagnosis code
    
    Args:
        code: ICD-10 code to validate (e.g., E11.9)
    
    Returns:
        Validation result with code details
    """
    service = MedicalCodesService(db_session)
    result = await service.validate_icd10_code(code)
    return ICD10ValidationResponse(**result)


@router.get("/cpt/{code}/validate", response_model=CPTValidationResponse)
async def validate_cpt_code(
    code: str,
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Validate a CPT procedure code
    
    Args:
        code: CPT code to validate (e.g., 99213)
    
    Returns:
        Validation result with code details
    """
    service = MedicalCodesService(db_session)
    result = await service.validate_cpt_code(code)
    return CPTValidationResponse(**result)


@router.get("/icd10/search", response_model=List[CodeSearchResult])
async def search_icd10_codes(
    q: str = Query(..., min_length=3, description="Search query (minimum 3 characters)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Full-text search for ICD-10 diagnosis codes
    
    Args:
        q: Search query (e.g., "diabetes", "heart attack")
        limit: Maximum number of results
    
    Returns:
        List of matching codes sorted by relevance
    """
    service = MedicalCodesService(db_session)
    results = await service.search_icd10_codes(q, limit)
    return [CodeSearchResult(**r) for r in results]


@router.get("/cpt/search", response_model=List[CodeSearchResult])
async def search_cpt_codes(
    q: str = Query(..., min_length=3, description="Search query (minimum 3 characters)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Full-text search for CPT procedure codes
    
    Args:
        q: Search query (e.g., "office visit", "blood test")
        limit: Maximum number of results
    
    Returns:
        List of matching codes sorted by relevance
    """
    service = MedicalCodesService(db_session)
    results = await service.search_cpt_codes(q, limit)
    return [CodeSearchResult(**r) for r in results]


@router.post("/medical-necessity/check", response_model=MedicalNecessityResponse)
async def check_medical_necessity(
    request: MedicalNecessityRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Check if a procedure is medically necessary given patient diagnoses
    
    This endpoint validates that the CPT procedure code is appropriate
    for the patient's diagnosis codes (ICD-10) based on medical necessity rules.
    
    Args:
        request: Medical necessity check request with CPT code, ICD-10 codes, and patient info
    
    Returns:
        Approval decision with reasoning and prior authorization requirements
    
    Example:
        ```json
        {
            "cpt_code": "99213",
            "icd10_codes": ["E11.9", "I10"],
            "insurance_type": "Medicare",
            "patient_age": 65,
            "patient_gender": "M"
        }
        ```
    """
    service = MedicalCodesService(db_session)
    result = await service.check_medical_necessity(
        cpt_code=request.cpt_code,
        icd10_codes=request.icd10_codes,
        insurance_type=request.insurance_type,
        patient_age=request.patient_age,
        patient_gender=request.patient_gender
    )
    return MedicalNecessityResponse(**result)


@router.get("/statistics", response_model=CodeStatistics)
async def get_code_statistics(
    db_session: AsyncSession = Depends(get_db_session)
):
    """
    Get statistics about loaded medical codes
    
    Returns:
        Counts of ICD-10, CPT, HCPCS codes and medical necessity rules
    """
    service = MedicalCodesService(db_session)
    stats = await service.get_code_statistics()
    return CodeStatistics(**stats)


# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check endpoint for medical codes API
    
    Returns:
        Status of the medical codes service
    """
    return {
        "status": "healthy",
        "service": "medical-codes-api",
        "version": "1.0.0"
    }

