"""
Denial Management Agent
Analyzes denied claims, categorizes denial reasons, and generates appeals
"""
from praisonaiagents import Agent, Task, Tool
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import json
import logging

logger = logging.getLogger(__name__)


# ===== Data Models =====

class DenialCategory(str):
    """Denial reason categories"""
    MISSING_INFO = "missing_information"
    AUTH_REQUIRED = "authorization_required"
    NOT_COVERED = "service_not_covered"
    CODING_ERROR = "coding_error"
    TIMELY_FILING = "timely_filing"
    DUPLICATE = "duplicate_claim"
    MEDICAL_NECESSITY = "medical_necessity"
    ELIGIBILITY = "eligibility_issue"
    OTHER = "other"


class DenialAnalysis(BaseModel):
    """Analysis of a denied claim"""
    claim_id: str
    denial_code: str
    denial_reason: str
    category: str
    root_cause: str
    correctable: bool
    appeal_recommended: bool
    appeal_success_probability: float = Field(ge=0.0, le=1.0)
    required_actions: List[str]
    required_documentation: List[str]
    estimated_recovery_amount: float
    priority: str  # high, medium, low
    
    class Config:
        use_enum_values = True


class AppealLetter(BaseModel):
    """Generated appeal letter"""
    claim_id: str
    appeal_type: str  # reconsideration, redetermination, appeal
    recipient_name: str
    recipient_address: str
    subject: str
    body: str
    supporting_documentation: List[str]
    created_date: datetime = Field(default_factory=datetime.now)
    deadline: datetime


class DenialMetrics(BaseModel):
    """Denial management metrics"""
    total_denials: int
    appeals_submitted: int
    appeals_won: int
    appeals_lost: int
    appeals_pending: int
    win_rate: float
    total_recovered: float
    avg_recovery_per_appeal: float
    common_denial_reasons: Dict[str, int]
    avg_appeal_turnaround_days: float


# ===== Tools =====

class DenialAnalysisTool(Tool):
    """Analyze denied claim to determine root cause and appeal strategy"""
    
    name = "analyze_denial"
    description = """Analyze a denied claim to identify root cause, determine if correctable,
    and recommend appeal strategy. Returns detailed analysis with action items."""
    
    def __init__(self, knowledge_base: Dict[str, Any]):
        super().__init__()
        self.knowledge_base = knowledge_base
        self.denial_codes = self._load_denial_codes()
        self.appeal_guidelines = self._load_appeal_guidelines()
    
    def _load_denial_codes(self) -> Dict[str, Dict]:
        """Load standard denial codes and their meanings"""
        return {
            # Common CARC (Claim Adjustment Reason Codes)
            "16": {
                "description": "Claim/service lacks information needed for adjudication",
                "category": DenialCategory.MISSING_INFO,
                "correctable": True,
                "common_fix": "Submit additional documentation"
            },
            "18": {
                "description": "Duplicate claim/service",
                "category": DenialCategory.DUPLICATE,
                "correctable": False,
                "common_fix": "Verify not duplicate, provide proof if error"
            },
            "29": {
                "description": "Time limit for filing has expired",
                "category": DenialCategory.TIMELY_FILING,
                "correctable": False,
                "common_fix": "Document extenuating circumstances"
            },
            "50": {
                "description": "Non-covered service",
                "category": DenialCategory.NOT_COVERED,
                "correctable": False,
                "common_fix": "Appeal with medical necessity justification"
            },
            "96": {
                "description": "Non-covered charge(s)",
                "category": DenialCategory.NOT_COVERED,
                "correctable": False,
                "common_fix": "Provide coverage policy exception"
            },
            "109": {
                "description": "Claim/service not covered by this payer",
                "category": DenialCategory.ELIGIBILITY,
                "correctable": True,
                "common_fix": "Verify patient eligibility at service date"
            },
            "197": {
                "description": "Precertification/authorization absent",
                "category": DenialCategory.AUTH_REQUIRED,
                "correctable": True,
                "common_fix": "Submit retroactive authorization"
            },
            "4": {
                "description": "Procedure code inconsistent with modifier",
                "category": DenialCategory.CODING_ERROR,
                "correctable": True,
                "common_fix": "Correct coding and resubmit"
            }
        }
    
    def _load_appeal_guidelines(self) -> Dict[str, Any]:
        """Load payer-specific appeal guidelines"""
        return {
            "allianz_egypt": {
                "first_level": "reconsideration",
                "deadline_days": 30,
                "submission_method": "electronic",
                "required_docs": ["appeal_letter", "clinical_notes", "medical_records"]
            },
            "metlife_egypt": {
                "first_level": "reconsideration",
                "deadline_days": 60,
                "submission_method": "portal",
                "required_docs": ["appeal_letter", "supporting_documentation"]
            },
            "axa_egypt": {
                "first_level": "appeal",
                "deadline_days": 45,
                "submission_method": "email",
                "required_docs": ["appeal_letter", "medical_justification"]
            },
            "hio_egypt": {
                "first_level": "administrative_review",
                "deadline_days": 90,
                "submission_method": "paper",
                "required_docs": ["official_appeal_form", "medical_records", "physician_statement"]
            }
        }
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Analyze denial"""
        try:
            data = json.loads(query)
            
            claim_id = data["claim_id"]
            denial_code = data["denial_code"]
            denial_reason = data.get("denial_reason", "")
            claim_amount = float(data.get("claim_amount", 0))
            payer = data.get("payer", "")
            service_date = data.get("service_date")
            
            # Look up denial code
            denial_info = self.denial_codes.get(
                denial_code,
                {
                    "description": denial_reason,
                    "category": DenialCategory.OTHER,
                    "correctable": True,
                    "common_fix": "Review and appeal with additional information"
                }
            )
            
            # Determine root cause
            root_cause = self._determine_root_cause(
                denial_code,
                denial_reason,
                data.get("claim_data", {})
            )
            
            # Assess appeal viability
            appeal_assessment = self._assess_appeal_viability(
                denial_info,
                claim_amount,
                service_date
            )
            
            # Generate action items
            actions = self._generate_actions(
                denial_info,
                appeal_assessment,
                payer
            )
            
            # Determine required documentation
            required_docs = self._determine_required_docs(
                denial_info["category"],
                payer
            )
            
            analysis = DenialAnalysis(
                claim_id=claim_id,
                denial_code=denial_code,
                denial_reason=denial_info["description"],
                category=denial_info["category"],
                root_cause=root_cause,
                correctable=denial_info["correctable"],
                appeal_recommended=appeal_assessment["recommend"],
                appeal_success_probability=appeal_assessment["success_probability"],
                required_actions=actions,
                required_documentation=required_docs,
                estimated_recovery_amount=claim_amount if appeal_assessment["recommend"] else 0,
                priority=self._determine_priority(claim_amount, appeal_assessment["success_probability"])
            )
            
            return {
                "status": "success",
                "analysis": analysis.dict()
            }
            
        except Exception as e:
            logger.error(f"Denial analysis failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _determine_root_cause(
        self,
        denial_code: str,
        denial_reason: str,
        claim_data: Dict
    ) -> str:
        """Determine root cause of denial"""
        # Pattern matching for common root causes
        if denial_code in ["16", "197"]:
            return "Missing or incomplete documentation at time of service"
        elif denial_code in ["18"]:
            return "Duplicate submission or billing error"
        elif denial_code in ["29"]:
            return "Claim submitted after payer's filing deadline"
        elif denial_code in ["4"]:
            return "Incorrect coding or modifier usage"
        elif denial_code in ["50", "96"]:
            return "Service not covered under patient's plan"
        elif denial_code in ["109"]:
            return "Patient not eligible for coverage on service date"
        else:
            return f"Denial code {denial_code}: {denial_reason}"
    
    def _assess_appeal_viability(
        self,
        denial_info: Dict,
        claim_amount: float,
        service_date: Optional[str]
    ) -> Dict[str, Any]:
        """Assess whether appeal is worth pursuing"""
        base_success_rate = {
            DenialCategory.MISSING_INFO: 0.85,
            DenialCategory.AUTH_REQUIRED: 0.70,
            DenialCategory.CODING_ERROR: 0.80,
            DenialCategory.MEDICAL_NECESSITY: 0.60,
            DenialCategory.NOT_COVERED: 0.30,
            DenialCategory.TIMELY_FILING: 0.20,
            DenialCategory.DUPLICATE: 0.40,
            DenialCategory.ELIGIBILITY: 0.65,
            DenialCategory.OTHER: 0.50
        }
        
        category = denial_info["category"]
        success_probability = base_success_rate.get(category, 0.50)
        
        # Adjust for claim amount (higher amounts worth more effort)
        if claim_amount > 10000:
            success_probability *= 1.1
        elif claim_amount < 1000:
            success_probability *= 0.9
        
        # Cap at 0.95
        success_probability = min(success_probability, 0.95)
        
        # Recommend appeal if:
        # 1. Correctable AND
        # 2. Success probability > 50% OR claim amount > 5000 EGP
        recommend = (
            denial_info["correctable"] and
            (success_probability > 0.5 or claim_amount > 5000)
        )
        
        return {
            "recommend": recommend,
            "success_probability": success_probability,
            "cost_benefit_ratio": claim_amount / 500 if recommend else 0  # Assume 500 EGP appeal cost
        }
    
    def _generate_actions(
        self,
        denial_info: Dict,
        appeal_assessment: Dict,
        payer: str
    ) -> List[str]:
        """Generate required actions"""
        actions = []
        
        if not appeal_assessment["recommend"]:
            actions.append("Close denial - appeal not recommended")
            actions.append("Analyze for process improvement")
            return actions
        
        # Standard actions based on category
        category = denial_info["category"]
        
        if category == DenialCategory.MISSING_INFO:
            actions.extend([
                "Gather missing documentation from medical records",
                "Request additional information from provider if needed",
                "Submit appeal with complete documentation"
            ])
        elif category == DenialCategory.AUTH_REQUIRED:
            actions.extend([
                "Check if retroactive authorization possible",
                "Gather clinical documentation justifying medical necessity",
                "Submit retroactive authorization request"
            ])
        elif category == DenialCategory.CODING_ERROR:
            actions.extend([
                "Review coding with certified coder",
                "Correct codes and modifiers",
                "Resubmit corrected claim"
            ])
        elif category == DenialCategory.MEDICAL_NECESSITY:
            actions.extend([
                "Obtain detailed physician notes and justification",
                "Review payer's medical policy for service",
                "Prepare medical necessity appeal with clinical rationale"
            ])
        else:
            actions.append("Prepare comprehensive appeal with all supporting documentation")
        
        # Add payer-specific action
        guidelines = self.appeal_guidelines.get(payer, {})
        if guidelines:
            deadline_days = guidelines.get("deadline_days", 30)
            actions.append(f"Submit appeal within {deadline_days} days via {guidelines.get('submission_method', 'appropriate channel')}")
        
        return actions
    
    def _determine_required_docs(self, category: str, payer: str) -> List[str]:
        """Determine required documentation"""
        base_docs = ["appeal_letter", "original_claim"]
        
        category_docs = {
            DenialCategory.MISSING_INFO: ["complete_medical_records", "lab_results", "imaging_reports"],
            DenialCategory.AUTH_REQUIRED: ["clinical_notes", "physician_order", "medical_justification"],
            DenialCategory.CODING_ERROR: ["corrected_claim", "coding_rationale"],
            DenialCategory.MEDICAL_NECESSITY: ["physician_statement", "clinical_guidelines", "peer_reviewed_literature"],
            DenialCategory.NOT_COVERED: ["coverage_policy", "exception_justification"],
            DenialCategory.ELIGIBILITY: ["eligibility_verification", "insurance_card_copy"],
        }
        
        docs = base_docs + category_docs.get(category, [])
        
        # Add payer-specific docs
        payer_guidelines = self.appeal_guidelines.get(payer, {})
        if payer_guidelines:
            docs.extend(payer_guidelines.get("required_docs", []))
        
        return list(set(docs))  # Remove duplicates
    
    def _determine_priority(self, amount: float, success_probability: float) -> str:
        """Determine appeal priority"""
        value_score = amount * success_probability
        
        if value_score > 10000:
            return "high"
        elif value_score > 2000:
            return "medium"
        else:
            return "low"


class AppealGenerationTool(Tool):
    """Generate appeal letter with appropriate language and structure"""
    
    name = "generate_appeal"
    description = """Generate a professional appeal letter based on denial analysis.
    Includes proper legal language, medical justification, and supporting arguments."""
    
    def __init__(self):
        super().__init__()
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """Load appeal letter templates"""
        return {
            "header": """
{recipient_name}
{recipient_address}

Re: Appeal of Claim Denial
Claim Number: {claim_id}
Patient Name: {patient_name}
Service Date: {service_date}
Denial Date: {denial_date}

Dear Claims Review Department:
""",
            "missing_info": """
I am writing to appeal the denial of the above-referenced claim, which was denied due to insufficient information. We have now gathered the complete documentation that was requested and respectfully request reconsideration of this claim.

The claim was originally submitted with the following information:
{original_submission}

We are now providing the following additional documentation:
{additional_docs}

This documentation clearly demonstrates that:
1. The service was medically necessary
2. The service was properly authorized
3. The service was performed as indicated

We respectfully request that you review this additional information and reconsider your denial decision.
""",
            "medical_necessity": """
I am writing to appeal the denial of the above-referenced claim on the basis of medical necessity. We strongly disagree with this determination and provide the following clinical rationale:

Clinical Presentation:
{clinical_presentation}

Medical Justification:
{medical_justification}

Supporting Evidence:
{supporting_evidence}

The treatment provided was not only medically necessary but represented the standard of care for this patient's condition. We have attached supporting documentation including:
{documentation_list}

Based on the clinical evidence provided, we respectfully request reconsideration and approval of this claim.
""",
            "authorization": """
I am writing to appeal the denial of the above-referenced claim due to lack of prior authorization. We request retroactive authorization based on the following circumstances:

{circumstances}

The service was emergent/urgent and could not be delayed for prior authorization without risking patient safety and outcomes. Clinical documentation demonstrates:
{clinical_documentation}

We respectfully request retroactive authorization and processing of this claim.
""",
            "closing": """
We believe the evidence provided supports the medical necessity and appropriateness of the services rendered. We request that you review this appeal and issue payment for the full amount of ${amount}.

If you require any additional information, please contact our office at {contact_info}.

We request a written response to this appeal within {response_days} business days as required by {applicable_law}.

Thank you for your prompt attention to this matter.

Sincerely,

{sender_name}
{sender_title}
{organization_name}
{contact_information}

Enclosures: {enclosures}
"""
        }
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Generate appeal letter"""
        try:
            data = json.loads(query)
            
            analysis = data["denial_analysis"]
            patient_info = data["patient_info"]
            payer_info = data["payer_info"]
            claim_info = data["claim_info"]
            
            # Determine appeal type and select template
            category = analysis["category"]
            template_key = self._select_template(category)
            
            # Generate letter body
            body = self._generate_body(
                template_key,
                analysis,
                patient_info,
                claim_info
            )
            
            # Generate complete letter
            letter = self._assemble_letter(
                analysis,
                patient_info,
                payer_info,
                claim_info,
                body
            )
            
            # Calculate deadline
            deadline = datetime.now() + timedelta(days=payer_info.get("appeal_deadline_days", 30))
            
            appeal_letter = AppealLetter(
                claim_id=analysis["claim_id"],
                appeal_type="reconsideration",
                recipient_name=payer_info["appeals_department"],
                recipient_address=payer_info["appeals_address"],
                subject=f"Appeal of Claim Denial - Claim #{analysis['claim_id']}",
                body=letter,
                supporting_documentation=analysis["required_documentation"],
                deadline=deadline
            )
            
            return {
                "status": "success",
                "appeal_letter": appeal_letter.dict()
            }
            
        except Exception as e:
            logger.error(f"Appeal generation failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _select_template(self, category: str) -> str:
        """Select appropriate template based on denial category"""
        template_map = {
            DenialCategory.MISSING_INFO: "missing_info",
            DenialCategory.MEDICAL_NECESSITY: "medical_necessity",
            DenialCategory.AUTH_REQUIRED: "authorization",
        }
        return template_map.get(category, "medical_necessity")
    
    def _generate_body(
        self,
        template_key: str,
        analysis: Dict,
        patient_info: Dict,
        claim_info: Dict
    ) -> str:
        """Generate letter body from template"""
        template = self.templates.get(template_key, "")
        
        # Populate template with actual data
        body = template.format(
            clinical_presentation=claim_info.get("clinical_presentation", ""),
            medical_justification=claim_info.get("medical_justification", ""),
            supporting_evidence=claim_info.get("supporting_evidence", ""),
            documentation_list=", ".join(analysis["required_documentation"]),
            circumstances=claim_info.get("circumstances", ""),
            clinical_documentation=claim_info.get("clinical_notes", ""),
            original_submission=claim_info.get("original_submission_summary", ""),
            additional_docs=", ".join(analysis["required_documentation"])
        )
        
        return body
    
    def _assemble_letter(
        self,
        analysis: Dict,
        patient_info: Dict,
        payer_info: Dict,
        claim_info: Dict,
        body: str
    ) -> str:
        """Assemble complete letter"""
        header = self.templates["header"].format(
            recipient_name=payer_info["appeals_department"],
            recipient_address=payer_info["appeals_address"],
            claim_id=analysis["claim_id"],
            patient_name=patient_info["name"],
            service_date=claim_info["service_date"],
            denial_date=claim_info.get("denial_date", "")
        )
        
        closing = self.templates["closing"].format(
            amount=claim_info.get("claim_amount", 0),
            contact_info="billing@hospital.com",
            response_days=payer_info.get("response_days", 30),
            applicable_law="Egyptian Insurance Law",
            sender_name="Billing Director",
            sender_title="Director of Revenue Cycle Management",
            organization_name="Hospital Name",
            contact_information="Phone: +20 xxx | Email: billing@hospital.com",
            enclosures=", ".join(analysis["required_documentation"])
        )
        
        return header + "\n" + body + "\n" + closing


# ===== Agent Definition =====

def create_denial_management_agent(tools: List[Tool]) -> Agent:
    """Create denial management agent"""
    return Agent(
        name="DenialManagementAgent",
        role="Denial Management Specialist",
        goal="Analyze denied claims, identify root causes, and generate winning appeals to maximize revenue recovery",
        backstory="""Expert denial management specialist with 15+ years of experience in healthcare revenue cycle.
        
Expertise includes:
- Comprehensive knowledge of CARC/RARC codes
- Payer-specific denial patterns and appeal processes
- Medical necessity criteria and clinical documentation requirements
- Regulatory compliance and appeal timelines
- Root cause analysis and process improvement

Track Record:
- 85% appeal success rate
- $5M+ annual revenue recovery
- Average appeal turnaround: 15 days
- Identified and resolved systemic denial issues resulting in 40% denial reduction

Specializations:
- Egyptian insurance payer policies (Allianz, MetLife, AXA, HIO)
- Complex medical necessity appeals
- Authorization and eligibility issues
- Coding error correction and resubmission
- Timely filing exception requests

Known for strategic appeal generation that combines clinical expertise with regulatory knowledge to maximize approval rates.""",
        tools=tools,
        verbose=True,
        memory=True,
        max_loops=3
    )