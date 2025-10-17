"""
Payment Posting Agent
Processes ERAs, posts payments, reconciles accounts, and identifies variances
"""
from praisonaiagents import Agent, Task, Tool
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)


# ===== Data Models =====

class PaymentType(str):
    """Payment types"""
    PATIENT = "patient"
    INSURANCE = "insurance"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"
    WRITEOFF = "writeoff"


class AdjustmentReason(str):
    """Adjustment reason codes"""
    CONTRACTUAL = "contractual_adjustment"
    DEDUCTIBLE = "patient_deductible"
    COINSURANCE = "patient_coinsurance"
    COPAY = "patient_copay"
    DENIAL = "claim_denial"
    SEQUESTRATION = "sequestration"
    OTHER = "other_adjustment"


class PaymentLine(BaseModel):
    """Individual payment line item"""
    line_number: int
    service_date: str
    procedure_code: str
    billed_amount: Decimal
    allowed_amount: Decimal
    paid_amount: Decimal
    patient_responsibility: Decimal
    adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    remark_codes: List[str] = Field(default_factory=list)


class ERA(BaseModel):
    """Electronic Remittance Advice"""
    era_id: str
    payer_id: str
    payer_name: str
    check_number: str
    check_date: datetime
    check_amount: Decimal
    claim_count: int
    claims: List[Dict[str, Any]]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


class PaymentPosting(BaseModel):
    """Payment posting record"""
    posting_id: str
    claim_id: str
    payment_type: PaymentType
    payment_date: datetime
    payment_amount: Decimal
    payment_method: str  # check, EFT, credit_card, cash
    check_number: Optional[str] = None
    adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    patient_balance: Decimal
    insurance_balance: Decimal
    total_balance: Decimal
    posted_by: str
    posted_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


class PaymentVariance(BaseModel):
    """Payment variance analysis"""
    claim_id: str
    expected_amount: Decimal
    actual_amount: Decimal
    variance_amount: Decimal
    variance_percentage: float
    variance_category: str  # underpayment, overpayment, correct
    reason: str
    requires_followup: bool
    recommended_action: str


class ReconciliationReport(BaseModel):
    """Payment reconciliation report"""
    report_date: datetime
    total_expected: Decimal
    total_posted: Decimal
    total_variance: Decimal
    variance_percentage: float
    claims_reconciled: int
    claims_with_variance: int
    underpayments: List[PaymentVariance]
    overpayments: List[PaymentVariance]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


# ===== Tools =====

class ERAProcessingTool(Tool):
    """Process Electronic Remittance Advice (ERA) files"""
    
    name = "process_era"
    description = """Parse ERA file and extract payment information for posting.
    Returns structured payment data ready for posting."""
    
    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Process ERA file"""
        try:
            data = json.loads(query)
            era_content = data.get("era_content", "")
            era_format = data.get("format", "835")  # X12 835 standard
            
            # Parse ERA content
            if era_format == "835":
                parsed_era = self._parse_x12_835(era_content)
            else:
                return {
                    "status": "error",
                    "error": f"Unsupported ERA format: {era_format}"
                }
            
            # Validate ERA
            validation = self._validate_era(parsed_era)
            if not validation["valid"]:
                return {
                    "status": "error",
                    "error": "ERA validation failed",
                    "details": validation["errors"]
                }
            
            # Store ERA
            era_id = self._store_era(parsed_era)
            
            return {
                "status": "success",
                "era": parsed_era,
                "era_id": era_id,
                "claims_count": len(parsed_era["claims"]),
                "total_amount": float(parsed_era["check_amount"])
            }
            
        except Exception as e:
            logger.error(f"ERA processing failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _parse_x12_835(self, content: str) -> Dict[str, Any]:
        """Parse X12 835 ERA format"""
        # Simplified parser - in production, use a library like pyx12
        lines = content.strip().split('~')
        
        era_data = {
            "payer_id": "",
            "payer_name": "",
            "check_number": "",
            "check_date": datetime.now(),
            "check_amount": Decimal("0.00"),
            "claims": []
        }
        
        current_claim = None
        
        for line in lines:
            segments = line.split('*')
            segment_id = segments[0] if segments else ""
            
            # BPR - Financial Information
            if segment_id == "BPR":
                era_data["check_amount"] = Decimal(segments[2])
                era_data["check_date"] = self._parse_date(segments[16])
                
            # N1 - Payer Identification
            elif segment_id == "N1" and segments[1] == "PR":
                era_data["payer_name"] = segments[2]
                era_data["payer_id"] = segments[4] if len(segments) > 4 else ""
            
            # CLP - Claim Payment Information
            elif segment_id == "CLP":
                if current_claim:
                    era_data["claims"].append(current_claim)
                
                current_claim = {
                    "claim_id": segments[1],
                    "claim_status": segments[2],
                    "billed_amount": Decimal(segments[3]),
                    "paid_amount": Decimal(segments[4]),
                    "patient_responsibility": Decimal(segments[5]) if len(segments) > 5 else Decimal("0"),
                    "service_lines": []
                }
            
            # SVC - Service Payment Information
            elif segment_id == "SVC" and current_claim:
                service_line = {
                    "procedure_code": segments[1].split(':')[1] if ':' in segments[1] else segments[1],
                    "billed_amount": Decimal(segments[2]),
                    "paid_amount": Decimal(segments[3]),
                    "units": int(segments[5]) if len(segments) > 5 else 1
                }
                current_claim["service_lines"].append(service_line)
            
            # CAS - Claim Adjustment
            elif segment_id == "CAS" and current_claim:
                adjustment = {
                    "group_code": segments[1],
                    "reason_code": segments[2],
                    "amount": Decimal(segments[3])
                }
                if "adjustments" not in current_claim:
                    current_claim["adjustments"] = []
                current_claim["adjustments"].append(adjustment)
        
        # Add last claim
        if current_claim:
            era_data["claims"].append(current_claim)
        
        return era_data
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from ERA format"""
        try:
            # Common formats: CCYYMMDD
            return datetime.strptime(date_str, "%Y%m%d")
        except:
            return datetime.now()
    
    def _validate_era(self, era_data: Dict) -> Dict[str, Any]:
        """Validate ERA data"""
        errors = []
        
        if not era_data.get("payer_id"):
            errors.append("Missing payer ID")
        
        if not era_data.get("check_amount"):
            errors.append("Missing check amount")
        
        if not era_data.get("claims"):
            errors.append("No claims found in ERA")
        
        # Validate total
        claims_total = sum(
            Decimal(str(claim.get("paid_amount", 0)))
            for claim in era_data.get("claims", [])
        )
        
        if abs(claims_total - era_data.get("check_amount", 0)) > Decimal("0.01"):
            errors.append(f"Check amount mismatch: {era_data.get('check_amount')} vs {claims_total}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _store_era(self, era_data: Dict) -> str:
        """Store ERA in database"""
        era_id = f"ERA-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        # In production, save to database
        return era_id


class PaymentPostingTool(Tool):
    """Post payments and adjustments to patient accounts"""
    
    name = "post_payment"
    description = """Post payment to claim and update account balances.
    Handles insurance payments, patient payments, and adjustments."""
    
    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Post payment"""
        try:
            data = json.loads(query)
            
            claim_id = data["claim_id"]
            payment_type = data["payment_type"]
            payment_amount = Decimal(str(data["payment_amount"]))
            payment_date = datetime.fromisoformat(data.get("payment_date", datetime.now().isoformat()))
            adjustments = data.get("adjustments", [])
            
            # Get current claim balance
            claim_balance = self._get_claim_balance(claim_id)
            
            # Post payment
            posting = self._create_posting(
                claim_id,
                payment_type,
                payment_amount,
                payment_date,
                adjustments,
                data
            )
            
            # Update balances
            new_balances = self._update_balances(
                claim_balance,
                payment_amount,
                payment_type,
                adjustments
            )
            
            # Check for variance
            variance = self._check_variance(
                claim_id,
                claim_balance,
                payment_amount,
                adjustments
            )
            
            # Save posting
            posting_id = self._save_posting(posting, new_balances)
            
            return {
                "status": "success",
                "posting_id": posting_id,
                "payment_amount": float(payment_amount),
                "new_patient_balance": float(new_balances["patient"]),
                "new_insurance_balance": float(new_balances["insurance"]),
                "total_balance": float(new_balances["total"]),
                "variance": variance,
                "posting_details": posting.dict()
            }
            
        except Exception as e:
            logger.error(f"Payment posting failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_claim_balance(self, claim_id: str) -> Dict[str, Decimal]:
        """Get current claim balances"""
        # In production, query from database
        return {
            "billed": Decimal("1000.00"),
            "patient": Decimal("200.00"),
            "insurance": Decimal("800.00"),
            "paid": Decimal("0.00")
        }
    
    def _create_posting(
        self,
        claim_id: str,
        payment_type: str,
        amount: Decimal,
        payment_date: datetime,
        adjustments: List[Dict],
        data: Dict
    ) -> PaymentPosting:
        """Create payment posting record"""
        posting_id = f"POST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return PaymentPosting(
            posting_id=posting_id,
            claim_id=claim_id,
            payment_type=payment_type,
            payment_date=payment_date,
            payment_amount=amount,
            payment_method=data.get("payment_method", "check"),
            check_number=data.get("check_number"),
            adjustments=adjustments,
            patient_balance=Decimal("0"),  # Will be updated
            insurance_balance=Decimal("0"),  # Will be updated
            total_balance=Decimal("0"),  # Will be updated
            posted_by=data.get("posted_by", "system")
        )
    
    def _update_balances(
        self,
        current_balance: Dict[str, Decimal],
        payment_amount: Decimal,
        payment_type: str,
        adjustments: List[Dict]
    ) -> Dict[str, Decimal]:
        """Calculate new balances after posting"""
        new_balances = current_balance.copy()
        
        # Apply payment
        if payment_type == PaymentType.INSURANCE:
            new_balances["insurance"] -= payment_amount
        elif payment_type == PaymentType.PATIENT:
            new_balances["patient"] -= payment_amount
        
        # Apply adjustments
        for adj in adjustments:
            adj_amount = Decimal(str(adj.get("amount", 0)))
            adj_reason = adj.get("reason", "")
            
            if "contractual" in adj_reason.lower():
                new_balances["insurance"] -= adj_amount
            elif "patient" in adj_reason.lower():
                new_balances["patient"] -= adj_amount
        
        new_balances["paid"] = (
            current_balance["billed"] -
            new_balances["patient"] -
            new_balances["insurance"]
        )
        
        new_balances["total"] = new_balances["patient"] + new_balances["insurance"]
        
        return new_balances
    
    def _check_variance(
        self,
        claim_id: str,
        current_balance: Dict,
        payment_amount: Decimal,
        adjustments: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Check for payment variance"""
        expected = current_balance.get("insurance", Decimal("0"))
        actual = payment_amount
        
        variance = expected - actual
        
        if abs(variance) > Decimal("1.00"):  # Threshold: 1 EGP
            return {
                "has_variance": True,
                "expected": float(expected),
                "actual": float(actual),
                "variance": float(variance),
                "percentage": float((variance / expected * 100) if expected > 0 else 0)
            }
        
        return {"has_variance": False}
    
    def _save_posting(self, posting: PaymentPosting, balances: Dict) -> str:
        """Save posting to database"""
        posting.patient_balance = balances["patient"]
        posting.insurance_balance = balances["insurance"]
        posting.total_balance = balances["total"]
        
        # In production, save to database
        return posting.posting_id


class ReconciliationTool(Tool):
    """Reconcile payments against expected amounts"""
    
    name = "reconcile_payments"
    description = """Reconcile posted payments against expected amounts.
    Identifies variances and generates reconciliation report."""
    
    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Reconcile payments"""
        try:
            data = json.loads(query)
            
            start_date = datetime.fromisoformat(data["start_date"])
            end_date = datetime.fromisoformat(data["end_date"])
            payer_id = data.get("payer_id")
            
            # Get payments in date range
            payments = self._get_payments(start_date, end_date, payer_id)
            
            # Analyze variances
            variances = []
            for payment in payments:
                variance = self._analyze_variance(payment)
                if variance:
                    variances.append(variance)
            
            # Generate report
            report = self._generate_report(payments, variances)
            
            return {
                "status": "success",
                "report": report.dict(),
                "total_claims": len(payments),
                "claims_with_variance": len(variances),
                "variance_percentage": report.variance_percentage
            }
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_payments(
        self,
        start_date: datetime,
        end_date: datetime,
        payer_id: Optional[str]
    ) -> List[Dict]:
        """Get payments for reconciliation"""
        # In production, query from database
        return []
    
    def _analyze_variance(self, payment: Dict) -> Optional[PaymentVariance]:
        """Analyze payment variance"""
        expected = Decimal(str(payment.get("expected_amount", 0)))
        actual = Decimal(str(payment.get("paid_amount", 0)))
        variance = expected - actual
        
        if abs(variance) < Decimal("1.00"):
            return None
        
        # Categorize variance
        if variance > 0:
            category = "underpayment"
            action = "Follow up with payer for additional payment"
        elif variance < 0:
            category = "overpayment"
            action = "Verify payment, may need to refund"
        else:
            category = "correct"
            action = "None"
        
        return PaymentVariance(
            claim_id=payment["claim_id"],
            expected_amount=expected,
            actual_amount=actual,
            variance_amount=variance,
            variance_percentage=float((variance / expected * 100) if expected > 0 else 0),
            variance_category=category,
            reason=payment.get("variance_reason", "Unknown"),
            requires_followup=abs(variance) > Decimal("50.00"),
            recommended_action=action
        )
    
    def _generate_report(
        self,
        payments: List[Dict],
        variances: List[PaymentVariance]
    ) -> ReconciliationReport:
        """Generate reconciliation report"""
        total_expected = sum(Decimal(str(p.get("expected_amount", 0))) for p in payments)
        total_posted = sum(Decimal(str(p.get("paid_amount", 0))) for p in payments)
        total_variance = total_expected - total_posted
        
        underpayments = [v for v in variances if v.variance_category == "underpayment"]
        overpayments = [v for v in variances if v.variance_category == "overpayment"]
        
        return ReconciliationReport(
            report_date=datetime.now(),
            total_expected=total_expected,
            total_posted=total_posted,
            total_variance=total_variance,
            variance_percentage=float((total_variance / total_expected * 100) if total_expected > 0 else 0),
            claims_reconciled=len(payments),
            claims_with_variance=len(variances),
            underpayments=underpayments,
            overpayments=overpayments
        )


# ===== Agent Definition =====

def create_payment_posting_agent(tools: List[Tool]) -> Agent:
    """Create payment posting agent"""
    return Agent(
        name="PaymentPostingAgent",
        role="Payment Posting Specialist",
        goal="Accurately post payments, reconcile accounts, and identify payment variances to ensure complete revenue capture",
        backstory="""Expert payment posting specialist with 12+ years of experience in healthcare revenue cycle.

Expertise includes:
- Electronic Remittance Advice (ERA) processing
- X12 835 transaction set parsing
- Payment variance analysis
- Account reconciliation
- Contractual adjustment verification
- Patient responsibility calculation

Track Record:
- 99.9% posting accuracy rate
- Average posting turnaround: Same day
- Identified $500K+ in underpayments through variance analysis
- Reconciles 1000+ payments daily

Specializations:
- Egyptian payer payment patterns
- Complex payment scenarios (partial payments, bundled services)
- Secondary insurance coordination
- Patient payment plans
- Credit balance management

Known for meticulous attention to detail and systematic approach that ensures every payment is posted correctly and all variances are identified and resolved.""",
        tools=tools,
        verbose=True,
        memory=True,
        max_loops=2
    )