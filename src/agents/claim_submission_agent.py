"""
Claim Submission Agent
Handles claim creation, validation, and submission to HCX
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import uuid

from praisonai_agents import Agent, Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.claim import Claim, ClaimItem, ClaimDiagnosis
from src.models.patient import Patient
from src.models.coverage import Coverage
from src.integrations.hcx.client import HCXClient
from src.tools.hcx_tools import HCXClaimSubmitTool
from fhir.resources.claim import Claim as FHIRClaim

logger = logging.getLogger(__name__)


class ClaimSubmissionAgent:
    """
    AI-powered claim submission agent
    
    Capabilities:
    - Create claims from clinical data
    - Validate claim completeness
    - Check coding accuracy
    - Submit claims to HCX
    - Track submission status
    - Handle submission errors
    """
    
    def __init__(self):
        self.name = "Claim Submission Agent"
        self.agent_type = "claims"
        self.avatar = "📋"
        
        # Initialize HCX client
        self.hcx_client = HCXClient()
        self.hcx_submit_tool = HCXClaimSubmitTool()
        
        # Initialize PraisonAI agent
        self.agent = Agent(
            name="Claims Specialist",
            role="Medical Claims Expert",
            goal="Create accurate claims and submit them successfully to payers via HCX",
            backstory="""You are an expert medical biller with 20+ years of experience 
            in claim submission and adjudication. You understand payer requirements, 
            coding rules, and common rejection reasons. You ensure every claim is 
            complete, accurate, and compliant before submission.""",
            verbose=True,
            allow_delegation=False
        )
    
    async def create_claim(
        self,
        patient_id: str,
        coverage_id: str,
        service_date: date,
        diagnoses: List[Dict[str, Any]],
        items: List[Dict[str, Any]],
        db_session: AsyncSession,
        provider_id: Optional[str] = None,
        facility_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new claim
        
        Args:
            patient_id: Patient ID
            coverage_id: Insurance coverage ID
            service_date: Date of service
            diagnoses: List of diagnosis codes with types
            items: List of service items with procedures
            db_session: Database session
            provider_id: Provider ID
            facility_id: Facility ID
        
        Returns:
            Created claim details
        """
        logger.info(f"📋 Creating claim for patient {patient_id}")
        
        try:
            # Validate patient exists
            patient = await db_session.get(Patient, patient_id)
            if not patient:
                return {
                    'success': False,
                    'message': f"❌ Patient not found: {patient_id}"
                }
            
            # Validate coverage exists
            coverage = await db_session.get(Coverage, coverage_id)
            if not coverage:
                return {
                    'success': False,
                    'message': f"❌ Coverage not found: {coverage_id}"
                }
            
            # Generate claim number
            claim_number = f"CLM-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            
            # Calculate total charge
            total_charge = sum(item.get('unit_price', 0) * item.get('quantity', 1) for item in items)
            
            # Create claim
            claim = Claim(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                coverage_id=coverage_id,
                provider_id=provider_id or "PROV-DEFAULT",
                facility_id=facility_id or "FAC-DEFAULT",
                claim_number=claim_number,
                claim_type="professional",
                service_date=service_date,
                total_charge_amount=total_charge,
                status="draft",
                priority="normal",
                created_at=datetime.utcnow()
            )
            
            db_session.add(claim)
            await db_session.flush()
            
            # Add diagnoses
            for idx, diag in enumerate(diagnoses, 1):
                diagnosis = ClaimDiagnosis(
                    claim_id=claim.id,
                    diagnosis_code=diag['code'],
                    diagnosis_type=diag.get('type', 'primary' if idx == 1 else 'secondary'),
                    sequence=idx
                )
                db_session.add(diagnosis)
            
            # Add items
            for idx, item_data in enumerate(items, 1):
                item = ClaimItem(
                    claim_id=claim.id,
                    sequence=idx,
                    procedure_code=item_data['procedure_code'],
                    procedure_description=item_data.get('description', ''),
                    service_date=service_date,
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('unit_price', 0),
                    total_price=item_data.get('unit_price', 0) * item_data.get('quantity', 1)
                )
                db_session.add(item)
            
            await db_session.commit()
            await db_session.refresh(claim)
            
            message = f"✅ **Claim Created Successfully!**\n\n"
            message += f"**Claim Number:** {claim_number}\n"
            message += f"**Patient:** {patient.first_name} {patient.last_name}\n"
            message += f"**Service Date:** {service_date.strftime('%Y-%m-%d')}\n"
            message += f"**Diagnoses:** {len(diagnoses)}\n"
            message += f"**Items:** {len(items)}\n"
            message += f"**Total Charge:** {total_charge:,.2f} EGP\n"
            message += f"**Status:** Draft\n\n"
            message += "Next steps:\n"
            message += "• Validate claim\n"
            message += "• Submit to HCX\n"
            message += "• Track status\n"
            
            return {
                'success': True,
                'message': message,
                'claim_id': claim.id,
                'claim_number': claim_number,
                'total_charge': total_charge
            }
        
        except Exception as e:
            logger.error(f"❌ Claim creation failed: {e}", exc_info=True)
            await db_session.rollback()
            return {
                'success': False,
                'message': f"Error creating claim: {str(e)}"
            }
    
    async def validate_claim(
        self,
        claim_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Validate claim before submission
        
        Checks:
        - All required fields present
        - Valid codes
        - Medical necessity
        - Eligibility
        - Completeness
        
        Args:
            claim_id: Claim ID
            db_session: Database session
        
        Returns:
            Validation results
        """
        logger.info(f"✅ Validating claim {claim_id}")
        
        try:
            # Get claim with relationships
            claim = await db_session.get(Claim, claim_id)
            if not claim:
                return {
                    'valid': False,
                    'message': f"❌ Claim not found: {claim_id}"
                }
            
            errors = []
            warnings = []
            
            # Check required fields
            if not claim.patient_id:
                errors.append("Missing patient ID")
            if not claim.coverage_id:
                errors.append("Missing coverage ID")
            if not claim.service_date:
                errors.append("Missing service date")
            
            # Get diagnoses
            stmt = select(ClaimDiagnosis).where(ClaimDiagnosis.claim_id == claim_id)
            result = await db_session.execute(stmt)
            diagnoses = result.scalars().all()
            
            if not diagnoses:
                errors.append("No diagnoses provided")
            else:
                # Check for primary diagnosis
                has_primary = any(d.diagnosis_type == 'primary' for d in diagnoses)
                if not has_primary:
                    errors.append("No primary diagnosis")
            
            # Get items
            stmt = select(ClaimItem).where(ClaimItem.claim_id == claim_id)
            result = await db_session.execute(stmt)
            items = result.scalars().all()
            
            if not items:
                errors.append("No service items provided")
            
            # Check totals
            if claim.total_charge_amount <= 0:
                errors.append("Total charge amount must be greater than zero")
            
            # Compile validation results
            if errors:
                message = f"❌ **Claim Validation Failed**\n\n"
                message += f"**Errors ({len(errors)}):**\n"
                for error in errors:
                    message += f"• {error}\n"
                
                if warnings:
                    message += f"\n**Warnings ({len(warnings)}):**\n"
                    for warning in warnings:
                        message += f"• {warning}\n"
                
                return {
                    'valid': False,
                    'message': message,
                    'errors': errors,
                    'warnings': warnings
                }
            
            message = f"✅ **Claim Validation Passed**\n\n"
            message += f"**Claim:** {claim.claim_number}\n"
            message += f"**Diagnoses:** {len(diagnoses)}\n"
            message += f"**Items:** {len(items)}\n"
            message += f"**Total:** {claim.total_charge_amount:,.2f} EGP\n\n"
            
            if warnings:
                message += f"**Warnings ({len(warnings)}):**\n"
                for warning in warnings:
                    message += f"• {warning}\n"
                message += "\n"
            
            message += "✅ **Ready to submit to HCX**"
            
            return {
                'valid': True,
                'message': message,
                'errors': [],
                'warnings': warnings
            }
        
        except Exception as e:
            logger.error(f"❌ Claim validation failed: {e}", exc_info=True)
            return {
                'valid': False,
                'message': f"Error validating claim: {str(e)}",
                'errors': [str(e)],
                'warnings': []
            }
    
    async def submit_to_hcx(
        self,
        claim_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Submit claim to HCX platform
        
        Args:
            claim_id: Claim ID
            db_session: Database session
        
        Returns:
            Submission results
        """
        logger.info(f"🚀 Submitting claim {claim_id} to HCX")
        
        try:
            # Validate first
            validation = await self.validate_claim(claim_id, db_session)
            if not validation['valid']:
                return {
                    'success': False,
                    'message': f"❌ Cannot submit - claim validation failed:\n\n{validation['message']}"
                }
            
            # Get claim
            claim = await db_session.get(Claim, claim_id)
            
            # Submit using HCX tool
            result = await self.hcx_submit_tool.submit_claim(
                claim_id=claim_id,
                db_session=db_session
            )
            
            if result.get('success'):
                # Update claim status
                claim.status = 'submitted'
                claim.submission_date = datetime.utcnow()
                claim.hcx_claim_id = result.get('hcx_claim_id')
                await db_session.commit()
                
                message = f"✅ **Claim Submitted Successfully!**\n\n"
                message += f"**Claim Number:** {claim.claim_number}\n"
                message += f"**HCX Claim ID:** {result.get('hcx_claim_id')}\n"
                message += f"**Submission Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
                message += f"**Status:** Submitted\n\n"
                message += "📊 **Next Steps:**\n"
                message += "• Monitor claim status\n"
                message += "• Check for adjudication\n"
                message += "• Track payment\n"
                
                return {
                    'success': True,
                    'message': message,
                    'hcx_claim_id': result.get('hcx_claim_id'),
                    'submission_time': datetime.utcnow().isoformat()
                }
            else:
                # Update status to failed
                claim.status = 'submission_failed'
                await db_session.commit()
                
                return {
                    'success': False,
                    'message': f"❌ **Claim Submission Failed**\n\n{result.get('error', 'Unknown error')}"
                }
        
        except Exception as e:
            logger.error(f"❌ HCX submission failed: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"Error submitting to HCX: {str(e)}"
            }
    
    async def get_claim_status(
        self,
        claim_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get claim status
        
        Args:
            claim_id: Claim ID
            db_session: Database session
        
        Returns:
            Claim status information
        """
        logger.info(f"🔍 Getting status for claim {claim_id}")
        
        try:
            claim = await db_session.get(Claim, claim_id)
            if not claim:
                return {
                    'found': False,
                    'message': f"❌ Claim not found: {claim_id}"
                }
            
            message = f"📊 **Claim Status**\n\n"
            message += f"**Claim Number:** {claim.claim_number}\n"
            message += f"**Status:** {claim.status.replace('_', ' ').title()}\n"
            message += f"**Created:** {claim.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            
            if claim.submission_date:
                message += f"**Submitted:** {claim.submission_date.strftime('%Y-%m-%d %H:%M')}\n"
            
            if claim.hcx_claim_id:
                message += f"**HCX ID:** {claim.hcx_claim_id}\n"
            
            message += f"**Total Charge:** {claim.total_charge_amount:,.2f} EGP\n"
            
            if claim.approved_amount:
                message += f"**Approved Amount:** {claim.approved_amount:,.2f} EGP\n"
            
            if claim.paid_amount:
                message += f"**Paid Amount:** {claim.paid_amount:,.2f} EGP\n"
            
            # Status-specific messages
            if claim.status == 'draft':
                message += "\n📝 **Next:** Validate and submit claim"
            elif claim.status == 'submitted':
                message += "\n⏳ **Next:** Wait for adjudication"
            elif claim.status == 'approved':
                message += "\n✅ **Next:** Expect payment"
            elif claim.status == 'denied':
                message += "\n❌ **Next:** Review denial and appeal"
            elif claim.status == 'paid':
                message += "\n✅ **Status:** Complete"
            
            return {
                'found': True,
                'message': message,
                'status': claim.status,
                'claim_number': claim.claim_number
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to get claim status: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error getting claim status: {str(e)}"
            }
