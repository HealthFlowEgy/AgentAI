"""
Medical Code Service
Provides business logic for medical code lookups and validation
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding

from src.models.medical_codes import ICD10Code, CPTCode, MedicalNecessityRule


class MedicalCodeService:
    """Service for medical code operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def search_icd10(self, query: str, limit: int = 10) -> List[ICD10Code]:
        """Search ICD-10 codes"""
        return self.db.query(ICD10Code).filter(
            ICD10Code.description.ilike(f"%{query}%")
        ).limit(limit).all()
    
    def search_cpt(self, query: str, limit: int = 10) -> List[CPTCode]:
        """Search CPT codes"""
        return self.db.query(CPTCode).filter(
            CPTCode.description.ilike(f"%{query}%")
        ).limit(limit).all()
    
    def check_medical_necessity(
        self,
        icd10_code: str,
        cpt_code: str
    ) -> Dict[str, Any]:
        """Check if procedure is medically necessary for diagnosis"""
        
        # Query medical necessity rules
        rule = self.db.query(MedicalNecessityRule).filter(
            MedicalNecessityRule.cpt_code == cpt_code,
            MedicalNecessityRule.icd10_codes.contains([icd10_code])
        ).first()
        
        if rule:
            return {
                "necessary": True,
                "rule_id": rule.id,
                "rule_description": rule.rule_description,
                "frequency_limit": rule.frequency_limit
            }
        
        # Default: assume necessary if no specific rule
        return {
            "necessary": True,
            "reason": "No specific contraindication found",
            "requires_documentation": False
        }
    
    def to_fhir_codeable_concept(
        self,
        code: str,
        code_system: str,
        display: str
    ) -> CodeableConcept:
        """Convert to FHIR CodeableConcept"""
        
        system_map = {
            "icd10": "http://hl7.org/fhir/sid/icd-10",
            "cpt": "http://www.ama-assn.org/go/cpt"
        }
        
        return CodeableConcept(
            coding=[Coding(
                system=system_map.get(code_system, code_system),
                code=code,
                display=display
            )],
            text=display
        )

