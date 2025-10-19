"""
Medical Coding Agent
Helps users find ICD-10 and CPT codes using AI and database search
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from praisonai_agents import Agent, Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from src.models.medical_codes import ICD10Code, CPTCode, MedicalNecessityRule
from src.services.medical_codes_service import MedicalCodesService

logger = logging.getLogger(__name__)


class MedicalCodingAgent:
    """
    AI-powered medical coding agent
    
    Capabilities:
    - Search ICD-10 diagnosis codes
    - Search CPT procedure codes
    - Validate code combinations
    - Check medical necessity
    - Suggest appropriate codes
    - Explain code meanings
    """
    
    def __init__(self):
        self.name = "Medical Coding Agent"
        self.agent_type = "coding"
        self.avatar = "🏥"
        
        # Initialize PraisonAI agent
        self.agent = Agent(
            name="Medical Coding Specialist",
            role="Medical Coding Expert",
            goal="Help users find accurate ICD-10 and CPT codes for medical procedures and diagnoses",
            backstory="""You are an expert medical coder with 15+ years of experience. 
            You have deep knowledge of ICD-10-CM, CPT, and HCPCS coding systems. 
            You help healthcare providers select the most accurate and specific codes 
            for diagnoses and procedures, ensuring proper reimbursement and compliance.""",
            verbose=True,
            allow_delegation=False
        )
    
    async def search_icd10(
        self,
        query: str,
        db_session: AsyncSession,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for ICD-10 diagnosis codes
        
        Args:
            query: Search query (code or description)
            db_session: Database session
            limit: Maximum results
        
        Returns:
            Search results with codes and descriptions
        """
        logger.info(f"🔍 Searching ICD-10 codes: {query}")
        
        try:
            service = MedicalCodesService(db_session)
            results = await service.search_icd10_codes(query, limit=limit)
            
            if not results:
                return {
                    'found': False,
                    'message': f"No ICD-10 codes found for '{query}'. Try:\n"
                               "• Using different keywords\n"
                               "• Being more specific\n"
                               "• Checking spelling\n\n"
                               "Example searches: 'diabetes', 'E11.9', 'hypertension'",
                    'results': []
                }
            
            # Format results for display
            formatted_results = []
            for code in results:
                formatted_results.append({
                    'code': code['code'],
                    'description': code['description'],
                    'category': code['category'],
                    'billable': code['billable'],
                    'valid_for_coding': code['valid_for_coding']
                })
            
            message = f"📋 **Found {len(results)} ICD-10 code{'' if len(results) == 1 else 's'}:**\n\n"
            
            for idx, code in enumerate(formatted_results, 1):
                billable_icon = "✅" if code['billable'] else "⚠️"
                message += f"**{idx}. {code['code']}** {billable_icon}\n"
                message += f"   {code['description']}\n"
                message += f"   Category: {code['category']}\n"
                if not code['billable']:
                    message += f"   ⚠️ Not billable - use more specific code\n"
                message += "\n"
            
            return {
                'found': True,
                'message': message,
                'results': formatted_results,
                'count': len(results)
            }
        
        except Exception as e:
            logger.error(f"❌ ICD-10 search failed: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error searching codes: {str(e)}",
                'results': []
            }
    
    async def search_cpt(
        self,
        query: str,
        db_session: AsyncSession,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for CPT procedure codes
        
        Args:
            query: Search query
            db_session: Database session
            category: Optional category filter (E/M, Surgery, etc.)
            limit: Maximum results
        
        Returns:
            Search results with codes and descriptions
        """
        logger.info(f"🔍 Searching CPT codes: {query} (category: {category})")
        
        try:
            service = MedicalCodesService(db_session)
            results = await service.search_cpt_codes(query, category=category, limit=limit)
            
            if not results:
                return {
                    'found': False,
                    'message': f"No CPT codes found for '{query}'. Try:\n"
                               "• Using procedure names\n"
                               "• Searching by category\n"
                               "• Using 5-digit codes\n\n"
                               "Example: 'office visit', '99213', 'surgery'",
                    'results': []
                }
            
            # Format results
            formatted_results = []
            for code in results:
                formatted_results.append({
                    'code': code['code'],
                    'description': code['description'],
                    'category': code['category'],
                    'rvu': code.get('rvu', 0),
                    'work_rvu': code.get('work_rvu', 0)
                })
            
            message = f"📋 **Found {len(results)} CPT code{'' if len(results) == 1 else 's'}:**\n\n"
            
            for idx, code in enumerate(formatted_results, 1):
                message += f"**{idx}. {code['code']}** - {code['category']}\n"
                message += f"   {code['description']}\n"
                if code['rvu'] > 0:
                    message += f"   RVU: {code['rvu']:.2f}\n"
                message += "\n"
            
            return {
                'found': True,
                'message': message,
                'results': formatted_results,
                'count': len(results)
            }
        
        except Exception as e:
            logger.error(f"❌ CPT search failed: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error searching codes: {str(e)}",
                'results': []
            }
    
    async def validate_code_pair(
        self,
        icd10_code: str,
        cpt_code: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Validate ICD-10 and CPT code combination for medical necessity
        
        Args:
            icd10_code: ICD-10 diagnosis code
            cpt_code: CPT procedure code
            db_session: Database session
        
        Returns:
            Validation result with medical necessity check
        """
        logger.info(f"✅ Validating: {icd10_code} + {cpt_code}")
        
        try:
            service = MedicalCodesService(db_session)
            
            # Validate both codes exist
            icd_valid, icd_info = await service.validate_icd10_code(icd10_code)
            cpt_valid, cpt_info = await service.validate_cpt_code(cpt_code)
            
            if not icd_valid:
                return {
                    'valid': False,
                    'message': f"❌ Invalid ICD-10 code: **{icd10_code}**",
                    'details': {'icd10_valid': False, 'cpt_valid': cpt_valid}
                }
            
            if not cpt_valid:
                return {
                    'valid': False,
                    'message': f"❌ Invalid CPT code: **{cpt_code}**",
                    'details': {'icd10_valid': icd_valid, 'cpt_valid': False}
                }
            
            # Check medical necessity
            is_necessary = await service.check_medical_necessity(icd10_code, cpt_code)
            
            message = f"**Code Validation:**\n\n"
            message += f"✅ **ICD-10:** {icd10_code}\n"
            message += f"   {icd_info['description']}\n\n"
            message += f"✅ **CPT:** {cpt_code}\n"
            message += f"   {cpt_info['description']}\n\n"
            
            if is_necessary:
                message += "✅ **Medical Necessity:** SUPPORTED\n"
                message += "This code combination is medically appropriate and should be covered."
            else:
                message += "⚠️ **Medical Necessity:** NOT VERIFIED\n"
                message += "This combination may require additional documentation or may not be covered.\n\n"
                
                # Get suggested procedures
                suggestions = await service.get_suggested_procedures(icd10_code)
                if suggestions:
                    message += "**Suggested procedures for this diagnosis:**\n"
                    for sugg in suggestions[:3]:
                        message += f"• {sugg['code']} - {sugg['description']}\n"
            
            return {
                'valid': True,
                'medically_necessary': is_necessary,
                'message': message,
                'details': {
                    'icd10': icd_info,
                    'cpt': cpt_info,
                    'medical_necessity': is_necessary
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}", exc_info=True)
            return {
                'valid': False,
                'message': f"Error validating codes: {str(e)}",
                'details': {}
            }
    
    async def suggest_codes(
        self,
        clinical_description: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Suggest appropriate codes based on clinical description using AI
        
        Args:
            clinical_description: Natural language description
            db_session: Database session
        
        Returns:
            Suggested ICD-10 and CPT codes
        """
        logger.info(f"💡 Suggesting codes for: {clinical_description[:50]}...")
        
        try:
            # Use AI to extract key terms
            task = Task(
                description=f"""Analyze this clinical description and extract:
                1. Primary diagnosis/condition
                2. Any procedures mentioned
                3. Key medical terms
                
                Description: {clinical_description}
                
                Return as JSON with keys: diagnosis, procedures, keywords""",
                agent=self.agent,
                expected_output="JSON with diagnosis, procedures, and keywords"
            )
            
            # Execute task (simplified - in production would use full PraisonAI)
            # For now, extract keywords manually
            keywords = self._extract_keywords(clinical_description)
            
            service = MedicalCodesService(db_session)
            
            # Search for relevant codes
            icd_results = []
            cpt_results = []
            
            for keyword in keywords[:3]:  # Top 3 keywords
                icd = await service.search_icd10_codes(keyword, limit=3)
                cpt = await service.search_cpt_codes(keyword, limit=3)
                icd_results.extend(icd)
                cpt_results.extend(cpt)
            
            # Remove duplicates
            icd_unique = {code['code']: code for code in icd_results}.values()
            cpt_unique = {code['code']: code for code in cpt_results}.values()
            
            message = f"💡 **Code Suggestions:**\n\n"
            message += f"Based on: _{clinical_description[:100]}..._\n\n"
            
            if icd_unique:
                message += "**ICD-10 Diagnosis Codes:**\n"
                for idx, code in enumerate(list(icd_unique)[:5], 1):
                    message += f"{idx}. **{code['code']}** - {code['description']}\n"
                message += "\n"
            
            if cpt_unique:
                message += "**CPT Procedure Codes:**\n"
                for idx, code in enumerate(list(cpt_unique)[:5], 1):
                    message += f"{idx}. **{code['code']}** - {code['description']}\n"
                message += "\n"
            
            if not icd_unique and not cpt_unique:
                message += "⚠️ No matching codes found. Try:\n"
                message += "• Being more specific\n"
                message += "• Using medical terminology\n"
                message += "• Describing the condition differently\n"
            else:
                message += "💡 **Tip:** Validate code combinations for medical necessity before billing."
            
            return {
                'found': len(icd_unique) > 0 or len(cpt_unique) > 0,
                'message': message,
                'icd10_codes': list(icd_unique),
                'cpt_codes': list(cpt_unique)
            }
        
        except Exception as e:
            logger.error(f"❌ Code suggestion failed: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error suggesting codes: {str(e)}",
                'icd10_codes': [],
                'cpt_codes': []
            }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract medical keywords from text"""
        # Simple keyword extraction (in production, use NLP)
        common_words = {'the', 'a', 'an', 'in', 'on', 'at', 'for', 'with', 'of', 'to', 'and', 'or'}
        
        words = text.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in common_words]
        
        return keywords[:5]
    
    async def get_code_details(
        self,
        code: str,
        code_type: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific code
        
        Args:
            code: Medical code
            code_type: 'icd10' or 'cpt'
            db_session: Database session
        
        Returns:
            Detailed code information
        """
        logger.info(f"📖 Getting details for {code_type.upper()} code: {code}")
        
        try:
            service = MedicalCodesService(db_session)
            
            if code_type.lower() == 'icd10':
                is_valid, info = await service.validate_icd10_code(code)
                
                if not is_valid:
                    return {
                        'found': False,
                        'message': f"❌ ICD-10 code **{code}** not found in database."
                    }
                
                message = f"📖 **ICD-10 Code Details:**\n\n"
                message += f"**Code:** {info['code']}\n"
                message += f"**Description:** {info['description']}\n"
                message += f"**Category:** {info['category']}\n"
                message += f"**Subcategory:** {info.get('subcategory', 'N/A')}\n"
                message += f"**Billable:** {'✅ Yes' if info['billable'] else '⚠️ No'}\n"
                message += f"**Valid for Coding:** {'✅ Yes' if info['valid_for_coding'] else '❌ No'}\n\n"
                
                if not info['billable']:
                    message += "⚠️ **Note:** This code is not billable. You need to use a more specific code.\n"
                
                # Get related procedures
                suggestions = await service.get_suggested_procedures(code)
                if suggestions:
                    message += f"\n**Common procedures for this diagnosis:**\n"
                    for sugg in suggestions[:5]:
                        message += f"• {sugg['code']} - {sugg['description']}\n"
            
            elif code_type.lower() == 'cpt':
                is_valid, info = await service.validate_cpt_code(code)
                
                if not is_valid:
                    return {
                        'found': False,
                        'message': f"❌ CPT code **{code}** not found in database."
                    }
                
                message = f"📖 **CPT Code Details:**\n\n"
                message += f"**Code:** {info['code']}\n"
                message += f"**Description:** {info['description']}\n"
                message += f"**Category:** {info['category']}\n"
                message += f"**RVU:** {info.get('rvu', 0):.2f}\n"
                message += f"**Facility RVU:** {info.get('facility_rvu', 0):.2f}\n"
                message += f"**Non-Facility RVU:** {info.get('non_facility_rvu', 0):.2f}\n"
            
            else:
                return {
                    'found': False,
                    'message': f"❌ Invalid code type: {code_type}. Must be 'icd10' or 'cpt'."
                }
            
            return {
                'found': True,
                'message': message,
                'details': info
            }
        
        except Exception as e:
            logger.error(f"❌ Failed to get code details: {e}", exc_info=True)
            return {
                'found': False,
                'message': f"Error retrieving code details: {str(e)}"
            }
    
    async def batch_validate(
        self,
        icd10_codes: List[str],
        cpt_codes: List[str],
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Validate multiple codes at once
        
        Args:
            icd10_codes: List of ICD-10 codes
            cpt_codes: List of CPT codes
            db_session: Database session
        
        Returns:
            Validation results for all codes
        """
        logger.info(f"📋 Batch validating {len(icd10_codes)} ICD-10 and {len(cpt_codes)} CPT codes")
        
        try:
            service = MedicalCodesService(db_session)
            results = await service.batch_validate_codes(
                icd10_codes=icd10_codes,
                cpt_codes=cpt_codes
            )
            
            message = f"📋 **Batch Validation Results:**\n\n"
            
            # ICD-10 results
            if icd10_codes:
                message += "**ICD-10 Codes:**\n"
                for code in icd10_codes:
                    result = results['icd10'].get(code, {})
                    if result.get('valid'):
                        message += f"✅ {code} - Valid\n"
                    else:
                        message += f"❌ {code} - Invalid\n"
                message += "\n"
            
            # CPT results
            if cpt_codes:
                message += "**CPT Codes:**\n"
                for code in cpt_codes:
                    result = results['cpt'].get(code, {})
                    if result.get('valid'):
                        message += f"✅ {code} - Valid\n"
                    else:
                        message += f"❌ {code} - Invalid\n"
                message += "\n"
            
            # Summary
            icd_valid = sum(1 for r in results['icd10'].values() if r.get('valid'))
            cpt_valid = sum(1 for r in results['cpt'].values() if r.get('valid'))
            
            message += f"**Summary:**\n"
            message += f"• ICD-10: {icd_valid}/{len(icd10_codes)} valid\n"
            message += f"• CPT: {cpt_valid}/{len(cpt_codes)} valid\n"
            
            return {
                'success': True,
                'message': message,
                'results': results,
                'summary': {
                    'icd10_valid': icd_valid,
                    'icd10_total': len(icd10_codes),
                    'cpt_valid': cpt_valid,
                    'cpt_total': len(cpt_codes)
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Batch validation failed: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"Error during batch validation: {str(e)}",
                'results': {}
            }
