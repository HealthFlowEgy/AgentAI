"""
Enhanced unit tests for Medical Codes Service
Tests search, validation, medical necessity, and performance
"""

import pytest
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.medical_codes_service import MedicalCodesService
from src.models.medical_codes import ICD10Code, CPTCode, MedicalNecessityRule


@pytest.mark.asyncio
class TestMedicalCodesService:
    """Test suite for Medical Codes Service"""
    
    async def test_search_icd10_by_code(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test searching ICD-10 codes by exact code"""
        service = MedicalCodesService(db_session)
        
        results = await service.search_icd10_codes("E11.9")
        
        assert len(results) > 0
        assert results[0]["code"] == "E11.9"
        assert "diabetes" in results[0]["description"].lower()
    
    async def test_search_icd10_by_description(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test searching ICD-10 codes by description"""
        service = MedicalCodesService(db_session)
        
        results = await service.search_icd10_codes("diabetes")
        
        assert len(results) > 0
        assert any("diabetes" in r["description"].lower() for r in results)
    
    async def test_search_icd10_fuzzy_match(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test fuzzy matching for ICD-10 codes"""
        service = MedicalCodesService(db_session)
        
        # Typo in search
        results = await service.search_icd10_codes("diabtes")  # Missing 'e'
        
        # Should still find diabetes codes with fuzzy matching
        assert len(results) > 0
    
    async def test_search_cpt_by_code(
        self,
        db_session: AsyncSession,
        sample_cpt_codes: list[CPTCode]
    ):
        """Test searching CPT codes by exact code"""
        service = MedicalCodesService(db_session)
        
        results = await service.search_cpt_codes("99213")
        
        assert len(results) > 0
        assert results[0]["code"] == "99213"
        assert "office" in results[0]["description"].lower()
    
    async def test_search_cpt_by_category(
        self,
        db_session: AsyncSession,
        sample_cpt_codes: list[CPTCode]
    ):
        """Test filtering CPT codes by category"""
        service = MedicalCodesService(db_session)
        
        results = await service.search_cpt_codes(category="E/M")
        
        assert len(results) > 0
        assert all(r["category"] == "E/M" for r in results)
    
    async def test_validate_icd10_code_valid(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test validating valid ICD-10 code"""
        service = MedicalCodesService(db_session)
        
        is_valid, code_info = await service.validate_icd10_code("E11.9")
        
        assert is_valid is True
        assert code_info is not None
        assert code_info["code"] == "E11.9"
        assert code_info["billable"] is True
    
    async def test_validate_icd10_code_invalid(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test validating invalid ICD-10 code"""
        service = MedicalCodesService(db_session)
        
        is_valid, code_info = await service.validate_icd10_code("INVALID123")
        
        assert is_valid is False
        assert code_info is None
    
    async def test_validate_cpt_code_valid(
        self,
        db_session: AsyncSession,
        sample_cpt_codes: list[CPTCode]
    ):
        """Test validating valid CPT code"""
        service = MedicalCodesService(db_session)
        
        is_valid, code_info = await service.validate_cpt_code("99213")
        
        assert is_valid is True
        assert code_info is not None
        assert code_info["code"] == "99213"
    
    async def test_validate_cpt_code_invalid(
        self,
        db_session: AsyncSession,
        sample_cpt_codes: list[CPTCode]
    ):
        """Test validating invalid CPT code"""
        service = MedicalCodesService(db_session)
        
        is_valid, code_info = await service.validate_cpt_code("99999")
        
        assert is_valid is False
        assert code_info is None
    
    async def test_check_medical_necessity(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code],
        sample_cpt_codes: list[CPTCode]
    ):
        """Test medical necessity checking"""
        service = MedicalCodesService(db_session)
        
        # Create medical necessity rule
        rule = MedicalNecessityRule(
            icd10_code="E11.9",
            cpt_codes=["99213", "99214"],
            description="Diabetes management",
            effective_date=date.today()
        )
        db_session.add(rule)
        await db_session.commit()
        
        # Test valid combination
        is_necessary = await service.check_medical_necessity("E11.9", "99213")
        assert is_necessary is True
        
        # Test invalid combination
        is_necessary = await service.check_medical_necessity("E11.9", "71045")
        assert is_necessary is False
    
    async def test_get_suggested_procedures(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code],
        sample_cpt_codes: list[CPTCode]
    ):
        """Test getting suggested procedures for diagnosis"""
        service = MedicalCodesService(db_session)
        
        # Create medical necessity rule
        rule = MedicalNecessityRule(
            icd10_code="E11.9",
            cpt_codes=["99213", "99214", "82947"],
            description="Diabetes management",
            effective_date=date.today()
        )
        db_session.add(rule)
        await db_session.commit()
        
        procedures = await service.get_suggested_procedures("E11.9")
        
        assert len(procedures) > 0
        assert any(p["code"] == "99213" for p in procedures)
        assert any(p["code"] == "82947" for p in procedures)
    
    async def test_search_performance_under_100ms(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test that search completes in under 100ms"""
        service = MedicalCodesService(db_session)
        
        start = datetime.now()
        results = await service.search_icd10_codes("diabetes")
        elapsed = (datetime.now() - start).total_seconds() * 1000
        
        assert elapsed < 100, f"Search took {elapsed}ms, exceeds 100ms target"
        assert len(results) > 0
    
    async def test_batch_code_validation(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code],
        sample_cpt_codes: list[CPTCode]
    ):
        """Test validating multiple codes at once"""
        service = MedicalCodesService(db_session)
        
        icd10_codes = ["E11.9", "I10", "INVALID"]
        cpt_codes = ["99213", "99214", "99999"]
        
        results = await service.batch_validate_codes(
            icd10_codes=icd10_codes,
            cpt_codes=cpt_codes
        )
        
        assert results["icd10"]["E11.9"]["valid"] is True
        assert results["icd10"]["I10"]["valid"] is True
        assert results["icd10"]["INVALID"]["valid"] is False
        
        assert results["cpt"]["99213"]["valid"] is True
        assert results["cpt"]["99214"]["valid"] is True
        assert results["cpt"]["99999"]["valid"] is False
    
    async def test_get_code_hierarchy(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test getting code hierarchy"""
        service = MedicalCodesService(db_session)
        
        # Get all diabetes codes
        hierarchy = await service.get_icd10_hierarchy(category="Endocrine")
        
        assert len(hierarchy) > 0
        assert all(h["category"] == "Endocrine" for h in hierarchy)
    
    async def test_search_with_limit(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test search with result limit"""
        service = MedicalCodesService(db_session)
        
        results = await service.search_icd10_codes("", limit=2)
        
        assert len(results) <= 2
    
    async def test_search_pagination(
        self,
        db_session: AsyncSession,
        sample_icd10_codes: list[ICD10Code]
    ):
        """Test search pagination"""
        service = MedicalCodesService(db_session)
        
        # Get first page
        page1 = await service.search_icd10_codes("", limit=2, offset=0)
        
        # Get second page
        page2 = await service.search_icd10_codes("", limit=2, offset=2)
        
        # Pages should be different
        if len(page1) > 0 and len(page2) > 0:
            assert page1[0]["id"] != page2[0]["id"]
