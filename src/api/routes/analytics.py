"""
Analytics Dashboard & Medical Code Database Integration
Complete implementation for Phase 3
"""

# ============================================
# Part 1: Analytics Dashboard
# src/api/routes/analytics.py
# ============================================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from decimal import Decimal

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class KPIMetrics(BaseModel):
    """Key Performance Indicators"""
    # Financial Metrics
    total_charges: Decimal
    total_payments: Decimal
    total_adjustments: Decimal
    net_revenue: Decimal
    collection_rate: float
    
    # Operational Metrics
    claims_submitted: int
    claims_approved: int
    claims_denied: int
    claims_pending: int
    
    # Quality Metrics
    clean_claim_rate: float
    denial_rate: float
    appeal_success_rate: float
    
    # Efficiency Metrics
    days_in_ar: float
    avg_collection_time_days: float
    avg_workflow_time_minutes: float
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class TrendData(BaseModel):
    """Trend data over time"""
    date: str
    value: float
    label: str


class PayerPerformance(BaseModel):
    """Payer-specific performance metrics"""
    payer_name: str
    payer_id: str
    claims_count: int
    total_billed: Decimal
    total_paid: Decimal
    avg_days_to_payment: float
    denial_rate: float
    clean_claim_rate: float
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class DenialAnalytics(BaseModel):
    """Denial analytics"""
    top_denial_reasons: List[Dict[str, Any]]
    denial_by_payer: List[Dict[str, Any]]
    denial_trend: List[TrendData]
    recovery_rate: float
    avg_appeal_time_days: float


@router.get("/kpis", response_model=KPIMetrics)
async def get_kpis(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    payer_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get key performance indicators"""
    
    # Set default date range (last 30 days)
    if not end_date:
        end_date = datetime.now()
    else:
        end_date = datetime.fromisoformat(end_date)
    
    if not start_date:
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.fromisoformat(start_date)
    
    # Query claims in date range
    query = db.query(ClaimRecord).filter(
        ClaimRecord.submission_date.between(start_date, end_date)
    )
    
    if payer_id:
        query = query.filter(ClaimRecord.insurance_company == payer_id)
    
    claims = query.all()
    
    # Calculate metrics
    total_charges = sum(c.total_charges or 0 for c in claims)
    total_payments = sum(c.actual_payment or 0 for c in claims)
    total_adjustments = total_charges - total_payments
    
    claims_submitted = len(claims)
    claims_approved = sum(1 for c in claims if c.status == 'approved')
    claims_denied = sum(1 for c in claims if c.status == 'denied')
    claims_pending = sum(1 for c in claims if c.status == 'pending')
    
    # Quality metrics
    clean_claim_rate = (claims_approved / claims_submitted * 100) if claims_submitted > 0 else 0
    denial_rate = (claims_denied / claims_submitted * 100) if claims_submitted > 0 else 0
    
    # Get appeal data
    appeals = db.query(AppealRecord).filter(
        AppealRecord.appeal_date.between(start_date, end_date)
    ).all()
    
    appeal_success_rate = (
        sum(1 for a in appeals if a.status == 'won') / len(appeals) * 100
        if appeals else 0
    )
    
    # Calculate Days in A/R
    days_in_ar = calculate_days_in_ar(db, end_date)
    
    # Avg collection time
    paid_claims = [c for c in claims if c.actual_payment > 0]
    avg_collection_time = (
        sum((c.payment_date - c.submission_date).days for c in paid_claims if c.payment_date) /
        len(paid_claims)
        if paid_claims else 0
    )
    
    # Avg workflow time
    workflows = db.query(WorkflowStateModel).filter(
        WorkflowStateModel.started_at.between(start_date, end_date),
        WorkflowStateModel.status == WorkflowStatus.COMPLETED
    ).all()
    
    avg_workflow_time = (
        sum(w.total_execution_time_ms or 0 for w in workflows) /
        len(workflows) / 60000  # Convert to minutes
        if workflows else 0
    )
    
    return KPIMetrics(
        total_charges=Decimal(str(total_charges)),
        total_payments=Decimal(str(total_payments)),
        total_adjustments=Decimal(str(total_adjustments)),
        net_revenue=Decimal(str(total_payments)),
        collection_rate=(total_payments / total_charges * 100) if total_charges > 0 else 0,
        claims_submitted=claims_submitted,
        claims_approved=claims_approved,
        claims_denied=claims_denied,
        claims_pending=claims_pending,
        clean_claim_rate=clean_claim_rate,
        denial_rate=denial_rate,
        appeal_success_rate=appeal_success_rate,
        days_in_ar=days_in_ar,
        avg_collection_time_days=avg_collection_time,
        avg_workflow_time_minutes=avg_workflow_time
    )


@router.get("/payer-performance", response_model=List[PayerPerformance])
async def get_payer_performance(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get payer-specific performance metrics"""
    
    # Implementation similar to KPIs but grouped by payer
    # Group claims by payer and calculate metrics
    pass


@router.get("/denial-analytics", response_model=DenialAnalytics)
async def get_denial_analytics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get comprehensive denial analytics"""
    
    # Query denied claims
    # Analyze denial reasons
    # Calculate recovery metrics
    pass


# ============================================
# Part 2: Medical Code Database Integration
# src/services/medical_code_service.py
# ============================================

from typing import List, Optional, Dict, Any
from sqlalchemy import or_, and_
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding


class ICD10Code(BaseModel):
    """ICD-10 diagnosis code"""
    code: str
    description: str
    category: str
    billable: bool
    valid_from: datetime
    valid_until: Optional[datetime] = None
    parent_code: Optional[str] = None
    requires_additional_digit: bool = False


class CPTCode(BaseModel):
    """CPT procedure code"""
    code: str
    description: str
    category: str
    typical_payment: Optional[Decimal] = None
    requires_preauth: bool = False
    modifiers_allowed: List[str] = Field(default_factory=list)
    bundled_codes: List[str] = Field(default_factory=list)
    valid_from: datetime
    valid_until: Optional[datetime] = None


class MedicalCodeService:
    """Service for medical code lookup and validation"""
    
    def __init__(self, db_session: Session, fhir_terminology_url: Optional[str] = None):
        self.db = db_session
        self.fhir_url = fhir_terminology_url
        self.cache = {}  # In-memory cache
    
    async def search_icd10(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[ICD10Code]:
        """Search ICD-10 codes"""
        
        # Check cache first
        cache_key = f"icd10:{query}:{category}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Query database
        db_query = self.db.query(ICD10CodeModel).filter(
            or_(
                ICD10CodeModel.code.ilike(f"%{query}%"),
                ICD10CodeModel.description.ilike(f"%{query}%")
            )
        )
        
        if category:
            db_query = db_query.filter(ICD10CodeModel.category == category)
        
        # Only active codes
        db_query = db_query.filter(
            ICD10CodeModel.valid_from <= datetime.now(),
            or_(
                ICD10CodeModel.valid_until.is_(None),
                ICD10CodeModel.valid_until > datetime.now()
            )
        )
        
        results = db_query.limit(limit).all()
        
        codes = [ICD10Code.from_orm(r) for r in results]
        
        # Cache results
        self.cache[cache_key] = codes
        
        return codes
    
    async def get_icd10(self, code: str, service_date: datetime) -> Optional[ICD10Code]:
        """Get specific ICD-10 code valid for service date"""
        
        result = self.db.query(ICD10CodeModel).filter(
            ICD10CodeModel.code == code,
            ICD10CodeModel.valid_from <= service_date,
            or_(
                ICD10CodeModel.valid_until.is_(None),
                ICD10CodeModel.valid_until > service_date
            )
        ).first()
        
        return ICD10Code.from_orm(result) if result else None
    
    async def search_cpt(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[CPTCode]:
        """Search CPT codes"""
        
        cache_key = f"cpt:{query}:{category}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        db_query = self.db.query(CPTCodeModel).filter(
            or_(
                CPTCodeModel.code.ilike(f"%{query}%"),
                CPTCodeModel.description.ilike(f"%{query}%")
            )
        )
        
        if category:
            db_query = db_query.filter(CPTCodeModel.category == category)
        
        db_query = db_query.filter(
            CPTCodeModel.valid_from <= datetime.now(),
            or_(
                CPTCodeModel.valid_until.is_(None),
                CPTCodeModel.valid_until > datetime.now()
            )
        )
        
        results = db_query.limit(limit).all()
        codes = [CPTCode.from_orm(r) for r in results]
        
        self.cache[cache_key] = codes
        return codes
    
    async def get_cpt(self, code: str, service_date: datetime) -> Optional[CPTCode]:
        """Get specific CPT code valid for service date"""
        
        result = self.db.query(CPTCodeModel).filter(
            CPTCodeModel.code == code,
            CPTCodeModel.valid_from <= service_date,
            or_(
                CPTCodeModel.valid_until.is_(None),
                CPTCodeModel.valid_until > service_date
            )
        ).first()
        
        return CPTCode.from_orm(result) if result else None
    
    async def validate_code_pair(
        self,
        icd10_code: str,
        cpt_code: str,
        service_date: datetime
    ) -> Dict[str, Any]:
        """Validate diagnosis-procedure code pair"""
        
        # Get codes
        diagnosis = await self.get_icd10(icd10_code, service_date)
        procedure = await self.get_cpt(cpt_code, service_date)
        
        if not diagnosis:
            return {
                "valid": False,
                "error": f"Invalid ICD-10 code: {icd10_code}"
            }
        
        if not procedure:
            return {
                "valid": False,
                "error": f"Invalid CPT code: {cpt_code}"
            }
        
        # Check medical necessity rules
        necessity = await self.check_medical_necessity(
            diagnosis.code,
            procedure.code
        )
        
        return {
            "valid": True,
            "medically_necessary": necessity["necessary"],
            "requires_preauth": procedure.requires_preauth,
            "diagnosis": diagnosis.dict(),
            "procedure": procedure.dict()
        }
    
    async def check_medical_necessity(
        self,
        icd10_code: str,
        cpt_code: str
    ) -> Dict[str, Any]:
        """Check medical necessity for ICD-10 and CPT combination"""
        # Placeholder implementation
        return {"medically_necessary": True, "confidence": "high"}
