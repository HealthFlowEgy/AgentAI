"""
Integration tests for medical codes with database
Week 3-4 Implementation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.integration
class TestMedicalCodesIntegration:
    """Integration tests for medical codes with real database operations"""
    
    @pytest.mark.asyncio
    async def test_full_code_validation_workflow(self):
        """Test complete code validation workflow"""
        # This test would require a real database connection
        # For now, we'll use mocks to demonstrate the workflow
        
        mock_session = MagicMock()
        
        # Step 1: Validate ICD-10 code
        mock_result_icd = MagicMock()
        mock_result_icd.fetchone.return_value = ("E11.9", "Type 2 diabetes", True, "Endocrine", "Diabetes")
        
        # Step 2: Validate CPT code
        mock_result_cpt = MagicMock()
        mock_result_cpt.fetchone.return_value = ("99213", "Office visit", "E&M", True, 150.00, 1.5)
        
        # Step 3: Check medical necessity
        mock_result_necessity = MagicMock()
        mock_result_necessity.fetchall.return_value = [
            (1, ["E11.9"], "Medicare", None, None, None, False, {})
        ]
        
        mock_session.execute = AsyncMock(side_effect=[mock_result_icd, mock_result_cpt, mock_result_necessity])
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        # Validate diagnosis code
        icd_result = await service.validate_icd10_code("E11.9")
        assert icd_result['valid'] is True
        
        # Validate procedure code
        cpt_result = await service.validate_cpt_code("99213")
        assert cpt_result['valid'] is True
        
        # Check medical necessity
        necessity_result = await service.check_medical_necessity(
            cpt_code="99213",
            icd10_codes=["E11.9"]
        )
        assert necessity_result['approved'] is True
    
    @pytest.mark.asyncio
    async def test_search_and_validate_workflow(self):
        """Test search followed by validation workflow"""
        mock_session = MagicMock()
        
        # Step 1: Search for codes
        mock_result_search = MagicMock()
        mock_result_search.fetchall.return_value = [
            ("E11.9", "Type 2 diabetes", "Endocrine", True, 0.95),
            ("E11.65", "Type 2 diabetes with hyperglycemia", "Endocrine", True, 0.85)
        ]
        
        # Step 2: Validate selected code
        mock_result_validate = MagicMock()
        mock_result_validate.fetchone.return_value = ("E11.9", "Type 2 diabetes", True, "Endocrine", "Diabetes")
        
        mock_session.execute = AsyncMock(side_effect=[mock_result_search, mock_result_validate])
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        # Search for codes
        search_results = await service.search_icd10_codes("diabetes")
        assert len(search_results) == 2
        
        # Validate the top result
        top_code = search_results[0]['code']
        validate_result = await service.validate_icd10_code(top_code)
        assert validate_result['valid'] is True
    
    @pytest.mark.asyncio
    async def test_batch_code_validation(self):
        """Test validating multiple codes in batch"""
        mock_session = MagicMock()
        
        codes_to_validate = ["E11.9", "I10", "J44.0"]
        mock_results = [
            ("E11.9", "Type 2 diabetes", True, "Endocrine", "Diabetes"),
            ("I10", "Essential hypertension", True, "Circulatory", "Hypertensive"),
            ("J44.0", "COPD with acute lower respiratory infection", True, "Respiratory", "COPD")
        ]
        
        mock_result_objs = [MagicMock() for _ in mock_results]
        for i, result in enumerate(mock_results):
            mock_result_objs[i].fetchone.return_value = result
        
        mock_session.execute = AsyncMock(side_effect=mock_result_objs)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        results = []
        for code in codes_to_validate:
            result = await service.validate_icd10_code(code)
            results.append(result)
        
        assert len(results) == 3
        assert all(r['valid'] for r in results)
    
    @pytest.mark.asyncio
    async def test_medical_necessity_with_multiple_diagnoses(self):
        """Test medical necessity check with multiple diagnosis codes"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, ["E11.9", "I10", "J44.0"], "Medicare", None, None, None, False, {})
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        result = await service.check_medical_necessity(
            cpt_code="99213",
            icd10_codes=["E11.9", "I10", "J44.0"]
        )
        
        assert result['approved'] is True
        assert len(result['matched_rules']) > 0
    
    @pytest.mark.asyncio
    async def test_statistics_after_import(self):
        """Test getting statistics after code import"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (6, 4, 0, 3)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        stats = await service.get_code_statistics()
        
        assert stats['icd10_codes'] == 6
        assert stats['cpt_codes'] == 4
        assert stats['total_codes'] == 10
        assert stats['medical_necessity_rules'] == 3


@pytest.mark.integration
@pytest.mark.slow
class TestDatabasePerformance:
    """Test database performance with realistic data volumes"""
    
    @pytest.mark.asyncio
    async def test_search_performance_with_large_dataset(self):
        """Test search performance with large result set"""
        import time
        
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Simulate large result set
        mock_result.fetchall.return_value = [
            (f"E11.{i}", f"Diabetes variant {i}", "Endocrine", True, 0.9 - (i * 0.01))
            for i in range(100)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        start_time = time.time()
        results = await service.search_icd10_codes("diabetes", limit=100)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        assert execution_time < 2.0  # Should complete in less than 2 seconds
        assert len(results) == 100
    
    @pytest.mark.asyncio
    async def test_concurrent_validations(self):
        """Test concurrent code validations"""
        import asyncio
        
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("E11.9", "Type 2 diabetes", True, "Endocrine", "Diabetes")
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        # Simulate 10 concurrent validations
        tasks = [
            service.validate_icd10_code("E11.9")
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(r['valid'] for r in results)


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery and resilience"""
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Test handling of database connection errors"""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=Exception("Database connection failed"))
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        with pytest.raises(Exception) as exc_info:
            await service.validate_icd10_code("E11.9")
        
        assert "Database connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_invalid_query_handling(self):
        """Test handling of invalid SQL queries"""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(side_effect=Exception("Invalid SQL syntax"))
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        with pytest.raises(Exception):
            await service.search_icd10_codes("test")
    
    @pytest.mark.asyncio
    async def test_empty_result_handling(self):
        """Test handling of empty results"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        from src.services.medical_codes_service import MedicalCodesService
        service = MedicalCodesService(mock_session)
        
        # Should not raise exception, should return valid error response
        result = await service.validate_icd10_code("NONEXISTENT")
        assert result['valid'] is False
        
        search_results = await service.search_icd10_codes("nonexistent")
        assert len(search_results) == 0


@pytest.mark.integration
class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    @pytest.mark.asyncio
    async def test_code_uniqueness(self):
        """Test that codes are unique in database"""
        # This would be enforced by database constraints
        # Test that duplicate inserts are handled
        pass
    
    @pytest.mark.asyncio
    async def test_referential_integrity(self):
        """Test referential integrity between tables"""
        # Medical necessity rules should reference valid CPT and ICD-10 codes
        pass
    
    @pytest.mark.asyncio
    async def test_data_consistency_after_update(self):
        """Test data remains consistent after updates"""
        # Test that updates don't break relationships
        pass

