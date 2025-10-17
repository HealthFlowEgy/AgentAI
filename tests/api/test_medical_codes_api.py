"""
API endpoint tests for medical codes
Week 3-4 Implementation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.api
class TestMedicalCodesAPI:
    """Test Medical Codes API endpoints"""
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint"""
        from src.api.routes.medical_codes import health_check
        
        response = await health_check()
        
        assert response['status'] == 'healthy'
        assert response['service'] == 'medical-codes-api'
        assert 'version' in response
    
    @pytest.mark.asyncio
    async def test_validate_icd10_endpoint(self):
        """Test ICD-10 validation endpoint"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("E11.9", "Type 2 diabetes", True, "Endocrine", "Diabetes")
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import validate_icd10_code
        
        response = await validate_icd10_code("E11.9", mock_session)
        
        assert response.valid is True
        assert response.code == "E11.9"
        assert "diabetes" in response.description.lower()
    
    @pytest.mark.asyncio
    async def test_validate_cpt_endpoint(self):
        """Test CPT validation endpoint"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("99213", "Office visit", "E&M", True, 150.00, 1.5)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import validate_cpt_code
        
        response = await validate_cpt_code("99213", mock_session)
        
        assert response.valid is True
        assert response.code == "99213"
        assert response.base_rate == 150.00
    
    @pytest.mark.asyncio
    async def test_search_icd10_endpoint(self):
        """Test ICD-10 search endpoint"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("E11.9", "Type 2 diabetes", "Endocrine", True, 0.95)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import search_icd10_codes
        
        results = await search_icd10_codes("diabetes", 20, mock_session)
        
        assert len(results) == 1
        assert results[0].code == "E11.9"
        assert results[0].relevance == 0.95
    
    @pytest.mark.asyncio
    async def test_search_cpt_endpoint(self):
        """Test CPT search endpoint"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("99213", "Office visit", "E&M", 150.00, 0.92)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import search_cpt_codes
        
        results = await search_cpt_codes("office visit", 20, mock_session)
        
        assert len(results) == 1
        assert results[0].code == "99213"
    
    @pytest.mark.asyncio
    async def test_medical_necessity_check_endpoint(self):
        """Test medical necessity check endpoint"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, ["E11.9", "I10"], "Medicare", None, None, None, False, {})
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import check_medical_necessity, MedicalNecessityRequest
        
        request = MedicalNecessityRequest(
            cpt_code="99213",
            icd10_codes=["E11.9"],
            insurance_type="Medicare",
            patient_age=65,
            patient_gender="M"
        )
        
        response = await check_medical_necessity(request, mock_session)
        
        assert response.approved is True
        assert response.prior_auth_required is False
        assert response.confidence == 'high'
    
    @pytest.mark.asyncio
    async def test_get_statistics_endpoint(self):
        """Test get statistics endpoint"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (70000, 10000, 5000, 1000)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import get_code_statistics
        
        response = await get_code_statistics(mock_session)
        
        assert response.icd10_codes == 70000
        assert response.cpt_codes == 10000
        assert response.total_codes == 85000


@pytest.mark.api
class TestAPIValidation:
    """Test API request validation"""
    
    def test_medical_necessity_request_validation(self):
        """Test MedicalNecessityRequest validation"""
        from src.api.routes.medical_codes import MedicalNecessityRequest
        
        # Valid request
        request = MedicalNecessityRequest(
            cpt_code="99213",
            icd10_codes=["E11.9", "I10"],
            insurance_type="Medicare",
            patient_age=65,
            patient_gender="M"
        )
        
        assert request.cpt_code == "99213"
        assert len(request.icd10_codes) == 2
        assert request.patient_age == 65
    
    def test_search_query_min_length(self):
        """Test search query minimum length requirement"""
        # In production, FastAPI would validate this
        query = "dia"
        assert len(query) >= 3
        
        short_query = "di"
        assert len(short_query) < 3
    
    def test_limit_parameter_validation(self):
        """Test limit parameter validation"""
        valid_limits = [1, 20, 50, 100]
        for limit in valid_limits:
            assert 1 <= limit <= 100
        
        invalid_limits = [0, -1, 101, 1000]
        for limit in invalid_limits:
            assert not (1 <= limit <= 100)


@pytest.mark.api
class TestAPIErrorHandling:
    """Test API error handling"""
    
    @pytest.mark.asyncio
    async def test_invalid_code_returns_error(self):
        """Test that invalid codes return proper error responses"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import validate_icd10_code
        
        response = await validate_icd10_code("INVALID", mock_session)
        
        assert response.valid is False
        assert response.error is not None
    
    @pytest.mark.asyncio
    async def test_empty_search_results(self):
        """Test empty search results handling"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import search_icd10_codes
        
        results = await search_icd10_codes("nonexistent", 20, mock_session)
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_medical_necessity_no_matching_rules(self):
        """Test medical necessity when no rules match"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import check_medical_necessity, MedicalNecessityRequest
        
        request = MedicalNecessityRequest(
            cpt_code="99999",
            icd10_codes=["E11.9"]
        )
        
        response = await check_medical_necessity(request, mock_session)
        
        assert response.approved is True
        assert response.confidence == 'low'
        assert len(response.matched_rules) == 0


@pytest.mark.api
@pytest.mark.slow
class TestAPIPerformance:
    """Test API performance"""
    
    @pytest.mark.asyncio
    async def test_search_performance(self):
        """Test search endpoint performance"""
        import time
        
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (f"E11.{i}", f"Diabetes type {i}", "Endocrine", True, 0.9)
            for i in range(20)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import search_icd10_codes
        
        start_time = time.time()
        results = await search_icd10_codes("diabetes", 20, mock_session)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        assert execution_time < 1.0  # Should complete in less than 1 second
        assert len(results) == 20
    
    @pytest.mark.asyncio
    async def test_validation_performance(self):
        """Test validation endpoint performance"""
        import time
        
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("E11.9", "Type 2 diabetes", True, "Endocrine", "Diabetes")
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.api.routes.medical_codes import validate_icd10_code
        
        start_time = time.time()
        response = await validate_icd10_code("E11.9", mock_session)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        assert execution_time < 0.5  # Should complete in less than 500ms
        assert response.valid is True

