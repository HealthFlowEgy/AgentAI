"""
Insurance Verification Agent
Verifies insurance coverage and eligibility via HCX
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, date

from praisonai_agents import Agent, Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.patient import Patient
from src.models.coverage import Coverage
from src.integrations.hcx.client import HCXClient
from src.tools.hcx_tools import HCXEligibilityTool

logger = logging.getLogger(__name__)


class InsuranceVerificationAgent:
    """
    AI-powered insurance verification agent
    
    Capabilities:
    - Verify insurance eligibility via HCX
    - Check coverage benefits
    - Validate policy status
    - Determine copay/deductible
    - Check authorization requirements
    - Update coverage records
    """
    
    def __init__(self):
        self.name = "Insurance Verification Agent"
        self.agent_type = "verification"
        self.avatar = "💳"
        
        # Initialize HCX tools
        self.hcx_client = HCXClient()
        self.hcx_eligibility_tool = HCXEligibilityTool()
        
        # Initialize PraisonAI agent
        self.agent = Agent(
            name="Insurance Verification Specialist",
            role="Insurance Verification Expert",
            goal="Verify patient insurance coverage and benefits in real-time via HCX",
            backstory="""You are an expert insurance verifier with 10+ years of experience 
            in eligibility verification, benefits coordination, and authorization requirements. 
            You ensure accurate coverage information before services are rendered, preventing 
            claim denials and patient billing issues.""",
            verbose=True,
            allow_delegation=False
        )
    
    async def verify_eligibility(
        self,
        patient_id: str,
        coverage_id: Optional[str],
        service_date: date,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Verify insurance eligibility via HCX
        
        Args:
            patient_id: Patient ID
            coverage_id: Optional coverage ID (or will use active coverage)
            service_date: Date of service
            db_session: Database session
        
        Returns:
            Eligibility verification results
        """
        logger.info(f"💳 Verifying eligibility for patient {patient_id}")
        
        try:
            # Get patient
            patient = await db_session.get(Patient, patient_id)
            if not patient:
                return {
                    'success': False,
                    'message': f"❌ Patient not found: {patient_id}"
                }
            
            # Get coverage
            if coverage_id:
                coverage = await db_session.get(Coverage, coverage_id)
            else:
                # Find active coverage
                stmt = select(Coverage).where(
                    Coverage.patient_id == patient_id,
                    Coverage.status == 'active'
                ).order_by(Coverage.coverage_start_date.desc())
                result = await db_session.execute(stmt)
                coverage = result.scalars().first()
            
            if not coverage:
                return {
                    'success': False,
                    'message': f"❌ No active insurance coverage found for patient.\n\n"
                               "**Next steps:**\n"
                               "• Add insurance information\n"
                               "• Update coverage details\n"
                               "• Verify patient eligibility"
                }
            
            # Check HCX eligibility
            result = await self.hcx_eligibility_tool.check_eligibility(
                patient_id=patient_id,
                coverage_id=coverage.id,
                service_date=service_date,
                db_session=db_session
            )
            
            if not result.get('success'):
                return {
                    'success': False,
                    'message': f"❌ **Eligibility Check Failed**\n\n{result.get('error', 'Unknown error')}"
                }
            
            # Parse eligibility response
            eligibility_data = result.get('eligibility_data', {})
            
            # Update coverage with latest info
            if eligibility_data:
                coverage.last_verified = datetime.utcnow()
                coverage.verification_status = 'verified'
                await db_session.commit()
            
            # Build response message
            is_eligible = eligibility_data.get('is_active', False)
            
            if is_eligible:
                message = f"✅ **Insurance Coverage Active**\n\n"
            else:
                message = f"❌ **Insurance Coverage Inactive**\n\n"
            
            message += f"**Patient:** {patient.first_name} {patient.last_name}\n"
            message += f"**Policy Number:** {coverage.policy_number}\n"
            message += f"**Payer:** {coverage.payer_name}\n"
            message += f"**Member ID:** {coverage.subscriber_id}\n\n"
            
            message += f"**Coverage Period:**\n"
            message += f"• Start: {coverage.coverage_start_date.strftime('%Y-%m-%d')}\n"
            message += f"• End: {coverage.coverage_end_date.strftime('%Y-%m-%d')}\n\n"
            
            if is_eligible:
                message += f"**Benefits:**\n"
                
                # Coverage percentage
                coverage_pct = eligibility_data.get('coverage_percentage', 80)
                message += f"• Coverage: {coverage_pct}%\n"
                
                # Copay
                copay = eligibility_data.get('copay_amount', coverage.copay_amount)
                if copay:
                    message += f"• Copay: {copay:.2f} EGP\n"
                
                # Deductible
                deductible = eligibility_data.get('deductible_amount', coverage.deductible_amount)
                deductible_met = eligibility_data.get('deductible_met', coverage.deductible_met)
                if deductible:
                    message += f"• Deductible: {deductible:.2f} EGP ({deductible_met:.2f} met)\n"
                
                # Out of pocket max
                oop_max = eligibility_data.get('out_of_pocket_max', coverage.out_of_pocket_max)
                oop_met = eligibility_data.get('out_of_pocket_met', coverage.out_of_pocket_met)
                if oop_max:
                    message += f"• Out-of-Pocket Max: {oop_max:.2f} EGP ({oop_met:.2f} met)\n"
                
                message += f"\n**Authorization:**\n"
                requires_auth = eligibility_data.get('requires_authorization', False)
                if requires_auth:
                    message += "⚠️ Prior authorization required for certain services\n"
                else:
                    message += "✅ No prior authorization required\n"
                
                message += f"\n✅ **Patient is eligible for services on {service_date.strftime('%Y-%m-%d')}**"
            else:
                message += "❌ **Patient is NOT eligible**\n\n"
                message += "**Possible reasons:**\n"
                message += "• Coverage period expired\n"
                message += "• Policy terminated\n"
                message += "• Incorrect information\n\n"
                message += "**Next steps:**\n"
                message += "• Update coverage information\n"
                message += "• Contact insurance company\n"
                message += "• Verify patient details\n"
            
            return {
                'success': True,
                'eligible': is_eligible,
                'message': message,
                'coverage_data': {
                    'policy_number': coverage.policy_number,
                    'payer': coverage.payer_name,
                    'is_active': is_eligible,
                    'copay': copay if is_eligible else None,
                    'deductible': deductible if is_eligible else None,
                    'deductible_met': deductible_met if is_eligible else None,
                    'coverage_percentage': coverage_pct if is_eligible else None,
                    'requires_authorization': eligibility_data.get('requires_authorization', False)
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Eligibility verification failed: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"Error verifying eligibility: {str(e)}"
            }
    
    async def get_coverage_details(
        self,
        patient_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get detailed coverage information for patient
        
        Args:
            patient_id: Patient ID
            db_session: Database session
        
        Returns:
            Coverage details
        """
        logger.info(f"📋 Getting coverage details for patient {patient_id}")
        
        try:
            # Get patient
            patient = await db_session.get(Patient, patient_id)
            if not patient:
                return {
                    'found': False,
                    'message': f"❌ Patient not found: {patient_id}"
                }
            
            # Get all coverages
            stmt = select(Coverage).where(
                Coverage.patient_id == patient_id
            ).order_by(Coverage.coverage_start_date.desc())
            result = await db_session.execute(stmt)
            coverages = result.scalars().all()
            
            if not coverages:
                return {
                    'found': False,
                    'message': f"❌ No insurance coverage found for patient.\n\n"
                               "**Patient:** {patient.first_name} {patient.last_name}\n"
                               "**Patient ID:** {patient_id}\n\n"
                               "Please add insurance information to proceed."
                }
            
            message = f"📋 **Insurance Coverage Details**\n\n"
            message += f"**Patient:** {patient.first_name} {patient.last_name}\n"
            message += f"**DOB:** {patient.date_of_birth.strftime('%Y-%m-%d')}\n"
            message += f"**Member ID:** {coverages[0].subscriber_id}\n\n"
            
            for idx, coverage in enumerate(coverages, 1):
                status_emoji = "✅" if coverage.status == 'active' else "⏸️" if coverage.status == 'inactive' else "❌"
                
                message += f"**Policy {idx}:** {status_emoji}\n"
                message += f"• **Payer:** {coverage.payer_name}\n"
                message += f"• **Policy #:** {coverage.policy_number}\n"
                message += f"• **Status:** {coverage.status.title()}\n"
                message += f"• **Period:** {coverage.coverage_start_date.strftime('%Y-%m-%d')} to {coverage.coverage_end_date.strftime('%Y-%m-%d')}\n"
                
                if coverage.status == 'active':
                    message += f"• **Copay:** {coverage.copay_amount:.2f} EGP\n"
                    message += f"• **Deductible:** {coverage.deductible_amount:.2f} EGP ({coverage.deductible_met:.2f} met)\n"
                
                if coverage.last_verified:
                    message += f"• **Last Verified:** {coverage.last_verified.strftime('%Y-%m-%d %H:%M')}\n"
                
                message += "\n"
            
            return {
                'found': True,
                'message': message,
                'coverages': [
                    {
                        'coverage_id': c.id,
                        'payer_name': c.payer_name,
                        'policy_number': c.policy_number,
                        'status': c.status,
                        'is_active': c.status == 'active'
                    }
                    for c in coverages
                ]
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to get coverage details: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error retrieving coverage: {str(e)}"
            }
    
    async def check_authorization_requirements(
        self,
        service_type: str,
        procedure_codes: list[str],
        coverage_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Check if prior authorization is required
        
        Args:
            service_type: Type of service (inpatient, outpatient, etc.)
            procedure_codes: List of CPT codes
            coverage_id: Coverage ID
            db_session: Database session
        
        Returns:
            Authorization requirements
        """
        logger.info(f"🔐 Checking authorization requirements for {service_type}")
        
        try:
            coverage = await db_session.get(Coverage, coverage_id)
            if not coverage:
                return {
                    'found': False,
                    'message': f"❌ Coverage not found: {coverage_id}"
                }
            
            # In production, this would query HCX or payer-specific rules
            # For now, we'll use common authorization requirements
            
            requires_auth = False
            auth_procedures = []
            
            # Common procedures requiring authorization
            high_cost_procedures = ['99285', '99291', '99292']  # Emergency/critical care
            surgical_procedures = [c for c in procedure_codes if c.startswith(('1', '2', '3', '4', '5'))]
            
            for code in procedure_codes:
                if code in high_cost_procedures or code in surgical_procedures:
                    requires_auth = True
                    auth_procedures.append(code)
            
            message = f"🔐 **Authorization Requirements**\n\n"
            message += f"**Service Type:** {service_type.title()}\n"
            message += f"**Payer:** {coverage.payer_name}\n"
            message += f"**Procedures:** {', '.join(procedure_codes)}\n\n"
            
            if requires_auth:
                message += "⚠️ **Prior Authorization Required**\n\n"
                message += f"**Procedures requiring auth:**\n"
                for code in auth_procedures:
                    message += f"• {code}\n"
                message += "\n"
                message += "**Next steps:**\n"
                message += "1. Submit authorization request\n"
                message += "2. Provide clinical documentation\n"
                message += "3. Wait for approval (typically 1-3 business days)\n"
                message += "4. Obtain authorization number\n"
            else:
                message += "✅ **No Prior Authorization Required**\n\n"
                message += "You may proceed with scheduling the service."
            
            return {
                'found': True,
                'requires_authorization': requires_auth,
                'message': message,
                'procedures_requiring_auth': auth_procedures
            }
        
        except Exception as e:
            logger.error(f"❌ Authorization check failed: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error checking authorization: {str(e)}"
            }
    
    async def estimate_patient_responsibility(
        self,
        total_charges: float,
        coverage_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Estimate patient's financial responsibility
        
        Args:
            total_charges: Total charges for service
            coverage_id: Coverage ID
            db_session: Database session
        
        Returns:
            Estimated patient responsibility
        """
        logger.info(f"💰 Estimating patient responsibility for {total_charges:.2f} EGP")
        
        try:
            coverage = await db_session.get(Coverage, coverage_id)
            if not coverage:
                return {
                    'found': False,
                    'message': f"❌ Coverage not found: {coverage_id}"
                }
            
            # Calculate patient responsibility
            copay = coverage.copay_amount or 0
            deductible_remaining = max(0, (coverage.deductible_amount or 0) - (coverage.deductible_met or 0))
            
            # Apply deductible first
            amount_after_deductible = max(0, total_charges - deductible_remaining)
            deductible_applied = min(total_charges, deductible_remaining)
            
            # Apply coinsurance (assuming 80/20 split - 20% patient responsibility)
            coinsurance_rate = 0.20
            coinsurance_amount = amount_after_deductible * coinsurance_rate
            
            # Insurance pays
            insurance_pays = amount_after_deductible * (1 - coinsurance_rate)
            
            # Total patient responsibility
            patient_pays = copay + deductible_applied + coinsurance_amount
            
            # Check out-of-pocket max
            oop_remaining = (coverage.out_of_pocket_max or float('inf')) - (coverage.out_of_pocket_met or 0)
            if patient_pays > oop_remaining:
                patient_pays = oop_remaining
                insurance_pays = total_charges - patient_pays - copay
            
            message = f"💰 **Estimated Patient Responsibility**\n\n"
            message += f"**Total Charges:** {total_charges:,.2f} EGP\n\n"
            
            message += f"**Breakdown:**\n"
            message += f"• Copay: {copay:,.2f} EGP\n"
            message += f"• Deductible: {deductible_applied:,.2f} EGP\n"
            message += f"• Coinsurance (20%): {coinsurance_amount:,.2f} EGP\n"
            message += f"• **Patient Pays:** {patient_pays:,.2f} EGP\n\n"
            
            message += f"• **Insurance Pays:** {insurance_pays:,.2f} EGP\n\n"
            
            message += f"**Remaining Benefits:**\n"
            message += f"• Deductible Remaining: {max(0, deductible_remaining - deductible_applied):,.2f} EGP\n"
            message += f"• Out-of-Pocket Max Remaining: {max(0, oop_remaining - patient_pays):,.2f} EGP\n\n"
            
            message += "⚠️ **Note:** This is an estimate. Actual amounts may vary based on:\n"
            message += "• In-network vs. out-of-network\n"
            message += "• Contracted rates with provider\n"
            message += "• Claim adjudication\n"
            
            return {
                'found': True,
                'message': message,
                'estimate': {
                    'total_charges': total_charges,
                    'copay': copay,
                    'deductible': deductible_applied,
                    'coinsurance': coinsurance_amount,
                    'patient_pays': patient_pays,
                    'insurance_pays': insurance_pays
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Patient responsibility estimation failed: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error estimating patient responsibility: {str(e)}"
            }
