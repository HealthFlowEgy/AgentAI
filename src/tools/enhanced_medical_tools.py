"""
Enhanced Medical Coding Tools with Database Integration
Replaces mock data with real medical code databases
"""
from praisonaiagents import Tool
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
import json
import logging

from src.models.medical_codes import ICD10Code, CPTCode, MedicalNecessityRule
from src.services.database import get_db

logger = logging.getLogger(__name__)


class EnhancedICD10LookupTool(Tool):
    """
    Enhanced ICD-10 code lookup with database integration
    Searches 70,000+ ICD-10 codes
    """
    name: str = "enhanced_icd10_lookup"
    description: str = """
    Look up ICD-10 diagnosis codes from comprehensive database.
    Input: JSON with 'query' (diagnosis description or code)
    Output: List of matching ICD-10 codes with descriptions
    """
    
    async def _run(self, input_data: str) -> str:
        """Look up ICD-10 codes"""
        try:
            data = json.loads(input_data)
            query = data.get("query", "").strip()
            limit = data.get("limit", 10)
            
            if not query:
                return json.dumps({"error": "Query parameter required"})
            
            with get_db() as db:
                # Check if query is a code or description
                if len(query) <= 7 and query.replace(".", "").isalnum():
                    # Exact code lookup
                    results = db.query(ICD10Code).filter(
                        ICD10Code.code.ilike(f"{query}%")
                    ).limit(limit).all()
                else:
                    # Description search
                    results = db.query(ICD10Code).filter(
                        or_(
                            ICD10Code.description.ilike(f"%{query}%"),
                            ICD10Code.category.ilike(f"%{query}%")
                        )
                    ).limit(limit).all()
                
                codes = [
                    {
                        "code": r.code,
                        "description": r.description,
                        "category": r.category,
                        "billable": r.billable,
                        "chapter": r.chapter
                    }
                    for r in results
                ]
                
                return json.dumps({
                    "success": True,
                    "query": query,
                    "count": len(codes),
                    "codes": codes
                }, indent=2)
                
        except Exception as e:
            logger.error(f"ICD-10 lookup error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


class EnhancedCPTLookupTool(Tool):
    """
    Enhanced CPT code lookup with database integration
    Searches 10,000+ CPT procedure codes
    """
    name: str = "enhanced_cpt_lookup"
    description: str = """
    Look up CPT procedure codes from comprehensive database.
    Input: JSON with 'query' (procedure description or code)
    Output: List of matching CPT codes with descriptions and pricing
    """
    
    async def _run(self, input_data: str) -> str:
        """Look up CPT codes"""
        try:
            data = json.loads(input_data)
            query = data.get("query", "").strip()
            limit = data.get("limit", 10)
            
            if not query:
                return json.dumps({"error": "Query parameter required"})
            
            with get_db() as db:
                # Check if query is a code or description
                if query.isdigit() and len(query) == 5:
                    # Exact code lookup
                    results = db.query(CPTCode).filter(
                        CPTCode.code == query
                    ).limit(limit).all()
                else:
                    # Description search
                    results = db.query(CPTCode).filter(
                        or_(
                            CPTCode.description.ilike(f"%{query}%"),
                            CPTCode.category.ilike(f"%{query}%")
                        )
                    ).limit(limit).all()
                
                codes = [
                    {
                        "code": r.code,
                        "description": r.description,
                        "category": r.category,
                        "base_rvu": float(r.base_rvu) if r.base_rvu else None,
                        "facility_fee": float(r.facility_fee) if r.facility_fee else None,
                        "non_facility_fee": float(r.non_facility_fee) if r.non_facility_fee else None,
                        "common_modifiers": r.common_modifiers
                    }
                    for r in results
                ]
                
                return json.dumps({
                    "success": True,
                    "query": query,
                    "count": len(codes),
                    "codes": codes
                }, indent=2)
                
        except Exception as e:
            logger.error(f"CPT lookup error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


class EnhancedMedicalNecessityTool(Tool):
    """
    Enhanced medical necessity validation with database rules
    Validates ICD-10 to CPT code relationships
    """
    name: str = "enhanced_medical_necessity"
    description: str = """
    Validate medical necessity for procedure-diagnosis combinations.
    Input: JSON with 'cpt_code', 'icd10_codes' (list), optional 'payer_id'
    Output: Validation result with medical necessity determination
    """
    
    async def _run(self, input_data: str) -> str:
        """Validate medical necessity"""
        try:
            data = json.loads(input_data)
            cpt_code = data.get("cpt_code", "").strip()
            icd10_codes = data.get("icd10_codes", [])
            payer_id = data.get("payer_id")
            patient_age = data.get("patient_age")
            patient_gender = data.get("patient_gender")
            
            if not cpt_code or not icd10_codes:
                return json.dumps({"error": "cpt_code and icd10_codes required"})
            
            with get_db() as db:
                # Find applicable rules
                query = db.query(MedicalNecessityRule).filter(
                    MedicalNecessityRule.cpt_code == cpt_code,
                    MedicalNecessityRule.active == True
                )
                
                # Filter by payer if specified
                if payer_id:
                    query = query.filter(
                        or_(
                            MedicalNecessityRule.payer_id == payer_id,
                            MedicalNecessityRule.payer_id.is_(None)
                        )
                    )
                
                rules = query.all()
                
                if not rules:
                    return json.dumps({
                        "success": True,
                        "medically_necessary": True,
                        "reason": "No specific rules found - default to approved",
                        "confidence": "low"
                    })
                
                # Check each rule
                for rule in rules:
                    # Check ICD-10 codes
                    matching_codes = set(icd10_codes) & set(rule.icd10_codes)
                    
                    if matching_codes:
                        # Check age restrictions
                        if patient_age:
                            if rule.min_age and patient_age < rule.min_age:
                                continue
                            if rule.max_age and patient_age > rule.max_age:
                                continue
                        
                        # Check gender restrictions
                        if rule.gender_restriction and patient_gender:
                            if rule.gender_restriction.upper() != patient_gender.upper():
                                continue
                        
                        # Rule matched
                        return json.dumps({
                            "success": True,
                            "medically_necessary": True,
                            "matching_codes": list(matching_codes),
                            "rule_description": rule.rule_description,
                            "frequency_limit": rule.frequency_limit,
                            "frequency_period_days": rule.frequency_period_days,
                            "confidence": "high"
                        })
                
                # No rules matched
                return json.dumps({
                    "success": True,
                    "medically_necessary": False,
                    "reason": "No medical necessity rules matched",
                    "rules_checked": len(rules),
                    "confidence": "high"
                })
                
        except Exception as e:
            logger.error(f"Medical necessity validation error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})


class ChargeCalculatorTool(Tool):
    """
    Enhanced charge calculator with CPT pricing
    """
    name: str = "charge_calculator"
    description: str = """
    Calculate charges for procedures using CPT codes.
    Input: JSON with 'cpt_codes' (list), 'facility_type' (facility/non_facility)
    Output: Total charges with breakdown
    """
    
    async def _run(self, input_data: str) -> str:
        """Calculate charges"""
        try:
            data = json.loads(input_data)
            cpt_codes = data.get("cpt_codes", [])
            facility_type = data.get("facility_type", "facility")
            
            if not cpt_codes:
                return json.dumps({"error": "cpt_codes required"})
            
            with get_db() as db:
                total_charges = 0.0
                breakdown = []
                
                for cpt_code in cpt_codes:
                    cpt = db.query(CPTCode).filter(CPTCode.code == cpt_code).first()
                    
                    if cpt:
                        if facility_type == "facility" and cpt.facility_fee:
                            charge = float(cpt.facility_fee)
                        elif facility_type == "non_facility" and cpt.non_facility_fee:
                            charge = float(cpt.non_facility_fee)
                        else:
                            charge = 0.0
                        
                        total_charges += charge
                        breakdown.append({
                            "code": cpt_code,
                            "description": cpt.description,
                            "charge": charge
                        })
                    else:
                        breakdown.append({
                            "code": cpt_code,
                            "description": "Code not found",
                            "charge": 0.0
                        })
                
                return json.dumps({
                    "success": True,
                    "total_charges": round(total_charges, 2),
                    "facility_type": facility_type,
                    "breakdown": breakdown
                }, indent=2)
                
        except Exception as e:
            logger.error(f"Charge calculation error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

