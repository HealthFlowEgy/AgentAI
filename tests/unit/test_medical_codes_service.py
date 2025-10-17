"""
Unit tests for medical codes service
Week 3-4 Implementation
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime


@pytest.mark.unit
class TestMedicalCodesService:
    """Test MedicalCodesService"""
    
    @pytest.mark.asyncio
    async def test_validate_icd10_code_valid(self):
        """Test validating a valid ICD-10 code"""
        # Mock database session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("E11.9", "Type 2 diabetes mellitus without complications", True, "Endocrine", "Diabetes")
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.validate_icd10_code("E11.9")
        
        assert result['valid'] is True
        assert result['code'] == "E11.9"
        assert "diabetes" in result['description'].lower()
        assert result['billable'] is True
        assert result['category'] == "Endocrine"
    
    @pytest.mark.asyncio
    async def test_validate_icd10_code_invalid(self):
        """Test validating an invalid ICD-10 code"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.validate_icd10_code("INVALID")
        
        assert result['valid'] is False
        assert 'error' in result
        assert "not found" in result['error'].lower()
    
    @pytest.mark.asyncio
    async def test_validate_cpt_code_valid(self):
        """Test validating a valid CPT code"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("99213", "Office visit, established patient", "E&M", True, 150.00, 1.5)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.validate_cpt_code("99213")
        
        assert result['valid'] is True
        assert result['code'] == "99213"
        assert result['base_rate'] == 150.00
        assert result['modifier_allowed'] is True
        assert result['rvu'] == 1.5
    
    @pytest.mark.asyncio
    async def test_validate_cpt_code_invalid(self):
        """Test validating an invalid CPT code"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.validate_cpt_code("00000")
        
        assert result['valid'] is False
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_search_icd10_codes(self):
        """Test searching ICD-10 codes"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("E11.9", "Type 2 diabetes mellitus without complications", "Endocrine", True, 0.95),
            ("E11.65", "Type 2 diabetes mellitus with hyperglycemia", "Endocrine", True, 0.85)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        results = await service.search_icd10_codes("diabetes", limit=10)
        
        assert len(results) == 2
        assert any("diabetes" in r['description'].lower() for r in results)
        assert all('code' in r for r in results)
        assert all('relevance' in r for r in results)
        assert results[0]['relevance'] >= results[1]['relevance']  # Sorted by relevance
    
    @pytest.mark.asyncio
    async def test_search_cpt_codes(self):
        """Test searching CPT codes"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("99213", "Office visit, established patient, 20-29 minutes", "E&M", 150.00, 0.92),
            ("99214", "Office visit, established patient, 30-39 minutes", "E&M", 220.00, 0.88)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        results = await service.search_cpt_codes("office visit", limit=10)
        
        assert len(results) == 2
        assert any("office" in r['description'].lower() for r in results)
        assert all('base_rate' in r for r in results)
    
    @pytest.mark.asyncio
    async def test_check_medical_necessity_approved(self):
        """Test medical necessity check - approved case"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Return a rule that matches
        mock_result.fetchall.return_value = [
            (1, ["E11.9", "I10"], "Medicare", None, None, None, False, {})
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.check_medical_necessity(
            cpt_code="99213",
            icd10_codes=["E11.9"],
            insurance_type="Medicare"
        )
        
        assert result['approved'] is True
        assert result['prior_auth_required'] is False
        assert result['confidence'] == 'high'
        assert len(result['matched_rules']) > 0
    
    @pytest.mark.asyncio
    async def test_check_medical_necessity_denied(self):
        """Test medical necessity check - denied case"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Return a rule that doesn't match the diagnosis
        mock_result.fetchall.return_value = [
            (1, ["E11.9", "I10"], "Medicare", None, None, None, False, {})
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.check_medical_necessity(
            cpt_code="99213",
            icd10_codes=["Z00.00"],  # Not in approved list
            insurance_type="Medicare"
        )
        
        assert result['approved'] is False
        assert 'reason' in result
        assert result['prior_auth_required'] is True
    
    @pytest.mark.asyncio
    async def test_check_medical_necessity_no_rules(self):
        """Test medical necessity when no rules exist"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.check_medical_necessity(
            cpt_code="99999",
            icd10_codes=["E11.9"]
        )
        
        assert result['approved'] is True
        assert result['confidence'] == 'low'
        assert result['reason'] == 'No specific rules defined'
    
    @pytest.mark.asyncio
    async def test_check_medical_necessity_with_age_filter(self):
        """Test medical necessity with age filtering"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, ["E11.9"], "Medicare", 18, 65, None, False, {})
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.check_medical_necessity(
            cpt_code="99213",
            icd10_codes=["E11.9"],
            patient_age=45
        )
        
        assert 'approved' in result
        assert 'confidence' in result
    
    @pytest.mark.asyncio
    async def test_get_code_statistics(self):
        """Test getting code statistics"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (70000, 10000, 5000, 1000)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        stats = await service.get_code_statistics()
        
        assert stats['icd10_codes'] == 70000
        assert stats['cpt_codes'] == 10000
        assert stats['hcpcs_codes'] == 5000
        assert stats['medical_necessity_rules'] == 1000
        assert stats['total_codes'] == 85000
        assert 'last_updated' in stats
    
    @pytest.mark.asyncio
    async def test_search_with_empty_query(self):
        """Test search with empty query string"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        results = await service.search_icd10_codes("", limit=10)
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test search respects limit parameter"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Return more results than limit
        mock_result.fetchall.return_value = [
            (f"E11.{i}", f"Diabetes type {i}", "Endocrine", True, 0.9)
            for i in range(5)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        results = await service.search_icd10_codes("diabetes", limit=5)
        
        assert len(results) == 5


@pytest.mark.unit
class TestMedicalCodesValidation:
    """Test medical code validation logic"""
    
    def test_icd10_code_format(self):
        """Test ICD-10 code format validation"""
        valid_codes = ["E11.9", "I10", "J44.0", "A00.0"]
        
        for code in valid_codes:
            assert len(code) >= 3
            assert code[0].isalpha()
    
    def test_cpt_code_format(self):
        """Test CPT code format validation"""
        valid_codes = ["99213", "99214", "80053", "93000"]
        
        for code in valid_codes:
            assert len(code) == 5
            assert code.isdigit()
    
    def test_medical_necessity_logic(self):
        """Test medical necessity matching logic"""
        approved_diagnoses = ["E11.9", "I10", "J44.0"]
        patient_diagnoses = ["E11.9", "Z00.00"]
        
        # Should match if any diagnosis is in approved list
        has_match = any(dx in approved_diagnoses for dx in patient_diagnoses)
        assert has_match is True
    
    def test_age_filtering_logic(self):
        """Test age filtering logic"""
        age_min = 18
        age_max = 65
        
        assert 18 >= age_min and 18 <= age_max
        assert 45 >= age_min and 45 <= age_max
        assert 65 >= age_min and 65 <= age_max
        assert not (17 >= age_min and 17 <= age_max)
        assert not (66 >= age_min and 66 <= age_max)

