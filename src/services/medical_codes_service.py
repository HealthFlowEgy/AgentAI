"""
Medical codes service with validation and search
Week 1-2 Implementation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
import logging

logger = logging.getLogger(__name__)


class MedicalCodesService:
    """Service for medical code operations"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def validate_icd10_code(self, code: str) -> Dict[str, Any]:
        """
        Validate an ICD-10 diagnosis code
        
        Returns:
            {
                'valid': bool,
                'code': str,
                'description': str,
                'billable': bool,
                'category': str
            }
        """
        result = await self.db.execute(
            text("""
                SELECT code, description, is_billable, category, subcategory
                FROM icd10_codes
                WHERE UPPER(code) = UPPER(:code)
            """),
            {'code': code.strip()}
        )
        
        row = result.fetchone()
        
        if row:
            return {
                'valid': True,
                'code': row[0],
                'description': row[1],
                'billable': row[2],
                'category': row[3],
                'subcategory': row[4]
            }
        else:
            return {
                'valid': False,
                'code': code,
                'error': f'ICD-10 code {code} not found'
            }
    
    async def validate_cpt_code(self, code: str) -> Dict[str, Any]:
        """
        Validate a CPT procedure code
        
        Returns:
            {
                'valid': bool,
                'code': str,
                'description': str,
                'category': str,
                'modifier_allowed': bool,
                'base_rate': float
            }
        """
        result = await self.db.execute(
            text("""
                SELECT code, description, category, modifier_allowed, base_rate, rvu
                FROM cpt_codes
                WHERE code = :code
            """),
            {'code': code.strip()}
        )
        
        row = result.fetchone()
        
        if row:
            return {
                'valid': True,
                'code': row[0],
                'description': row[1],
                'category': row[2],
                'modifier_allowed': row[3],
                'base_rate': float(row[4]) if row[4] else None,
                'rvu': float(row[5]) if row[5] else None
            }
        else:
            return {
                'valid': False,
                'code': code,
                'error': f'CPT code {code} not found'
            }
    
    async def search_icd10_codes(
        self, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Full-text search for ICD-10 codes
        
        Args:
            query: Search query
            limit: Maximum results to return
        
        Returns:
            List of matching codes with relevance scores
        """
        result = await self.db.execute(
            text("""
                SELECT code, description, category, is_billable,
                       ts_rank(to_tsvector('english', description), query) as rank
                FROM icd10_codes, 
                     plainto_tsquery('english', :query) query
                WHERE to_tsvector('english', description) @@ query
                ORDER BY rank DESC
                LIMIT :limit
            """),
            {'query': query, 'limit': limit}
        )
        
        return [
            {
                'code': row[0],
                'description': row[1],
                'category': row[2],
                'billable': row[3],
                'relevance': float(row[4])
            }
            for row in result.fetchall()
        ]
    
    async def search_cpt_codes(
        self, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Full-text search for CPT codes"""
        result = await self.db.execute(
            text("""
                SELECT code, description, category, base_rate,
                       ts_rank(to_tsvector('english', description), query) as rank
                FROM cpt_codes, 
                     plainto_tsquery('english', :query) query
                WHERE to_tsvector('english', description) @@ query
                ORDER BY rank DESC
                LIMIT :limit
            """),
            {'query': query, 'limit': limit}
        )
        
        return [
            {
                'code': row[0],
                'description': row[1],
                'category': row[2],
                'base_rate': float(row[3]) if row[3] else None,
                'relevance': float(row[4])
            }
            for row in result.fetchall()
        ]
    
    async def check_medical_necessity(
        self,
        cpt_code: str,
        icd10_codes: List[str],
        insurance_type: Optional[str] = None,
        patient_age: Optional[int] = None,
        patient_gender: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if procedure is medically necessary given diagnoses
        
        Returns:
            {
                'approved': bool,
                'reason': str,
                'matched_rules': List[Dict],
                'prior_auth_required': bool,
                'confidence': str
            }
        """
        # Find matching rules
        result = await self.db.execute(
            text("""
                SELECT id, icd10_codes, insurance_type, age_min, age_max,
                       gender, prior_auth_required, metadata
                FROM medical_necessity_rules
                WHERE cpt_code = :cpt_code
                  AND (insurance_type IS NULL OR insurance_type = :insurance_type)
                  AND (age_min IS NULL OR :patient_age IS NULL OR :patient_age >= age_min)
                  AND (age_max IS NULL OR :patient_age IS NULL OR :patient_age <= age_max)
                  AND (gender IS NULL OR :patient_gender IS NULL OR gender = :patient_gender)
            """),
            {
                'cpt_code': cpt_code,
                'insurance_type': insurance_type,
                'patient_age': patient_age,
                'patient_gender': patient_gender
            }
        )
        
        rules = result.fetchall()
        
        if not rules:
            # No rules defined - approve by default but flag for review
            return {
                'approved': True,
                'reason': 'No specific rules defined',
                'matched_rules': [],
                'prior_auth_required': False,
                'confidence': 'low'
            }
        
        # Check if any ICD-10 codes match
        for rule in rules:
            rule_icd10_codes = rule[1]  # icd10_codes array
            
            # Check if any patient diagnosis matches rule
            if any(code in rule_icd10_codes for code in icd10_codes):
                return {
                    'approved': True,
                    'reason': 'Matches medical necessity criteria',
                    'matched_rules': [{
                        'rule_id': rule[0],
                        'approved_diagnoses': list(rule_icd10_codes),
                        'insurance_type': rule[2]
                    }],
                    'prior_auth_required': rule[6],
                    'confidence': 'high'
                }
        
        # No matching diagnoses
        return {
            'approved': False,
            'reason': 'No matching diagnosis codes for this procedure',
            'matched_rules': [],
            'prior_auth_required': True,
            'confidence': 'high',
            'suggestion': 'Review diagnosis codes or consider alternative procedures'
        }
    
    async def get_code_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded codes"""
        result = await self.db.execute(
            text("""
                SELECT 
                    (SELECT COUNT(*) FROM icd10_codes) as icd10_count,
                    (SELECT COUNT(*) FROM cpt_codes) as cpt_count,
                    (SELECT COUNT(*) FROM hcpcs_codes) as hcpcs_count,
                    (SELECT COUNT(*) FROM medical_necessity_rules) as rules_count
            """)
        )
        
        row = result.fetchone()
        
        return {
            'icd10_codes': row[0],
            'cpt_codes': row[1],
            'hcpcs_codes': row[2],
            'medical_necessity_rules': row[3],
            'total_codes': row[0] + row[1] + row[2],
            'last_updated': datetime.utcnow().isoformat()
        }

