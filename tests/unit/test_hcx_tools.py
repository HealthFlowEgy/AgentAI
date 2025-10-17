"""
Comprehensive test suite for HCX tools
Tests async functionality, FHIR validation, error handling, and retry logic
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import httpx
from src.tools.hcx_tools import (
    HCXEligibilityTool,
    HCXPreAuthTool,
    HCXClaimSubmitTool,
    HCXClaimStatusTool,
    TokenManager
)


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get.return_value = None
    redis.setex.return_value = True
    return redis


@pytest.fixture
def mock_token_manager(mock_redis):
    """Create mock token manager"""
    token_manager = TokenManager(
        hcx_url="http://test-hcx.com",
        username="test_user",
        password="test_pass",
        redis_client=mock_redis
    )
    token_manager._token = "test_token_12345"
    token_manager._token_expiry = datetime.now() + timedelta(hours=1)
    return token_manager


# ===== Token Manager Tests =====

@pytest.mark.asyncio
async def test_token_manager_returns_cached_token(mock_redis):
    """Test that TokenManager returns cached token from Redis"""
    mock_redis.get.return_value = b"cached_token_xyz"
    
    token_manager = TokenManager(
        "http://test.com",
        "user",
        "pass",
        mock_redis
    )
    
    token = await token_manager.get_valid_token()
    
    assert token == "cached_token_xyz"
    mock_redis.get.assert_called_once_with("hcx:auth_token")


@pytest.mark.asyncio
async def test_token_manager_refreshes_expired_token():
    """Test that TokenManager refreshes when token is expired"""
    token_manager = TokenManager(
        "http://test.com",
        "user",
        "pass"
    )
    token_manager._token = "old_token"
    token_manager._token_expiry = datetime.now() - timedelta(minutes=1)  # Expired
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_fresh_token",
            "expires_in": 3600
        }
        mock_response.raise_for_status = Mock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        
        token = await token_manager.get_valid_token()
        
        assert token == "new_fresh_token"
        assert token_manager._token == "new_fresh_token"


# ===== Eligibility Tool Tests =====

@pytest.mark.asyncio
async def test_eligibility_check_success(mock_token_manager):
    """Test successful eligibility check"""
    tool = HCXEligibilityTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    input_data = {
        "patient_id": "P123",
        "insurance_company": "allianz_egypt",
        "policy_number": "ALZ123456",
        "service_date": "2025-10-17"
    }
    
    mock_response = {
        "resourceType": "CoverageEligibilityResponse",
        "id": "resp-123",
        "status": "active",
        "patient": {"reference": "Patient/P123"},
        "insurance": [{
            "inforce": True,
            "item": [{
                "benefit": [{
                    "type": {
                        "coding": [{"code": "copay"}]
                    },
                    "usedMoney": {
                        "value": 50.0,
                        "currency": "EGP"
                    }
                }]
            }]
        }]
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_http_response = Mock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = Mock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_http_response
        )
        
        result = await tool._run(json.dumps(input_data))
        
        assert result["status"] == "success"
        assert result["eligible"] is True
        assert result["copay"] == 50.0


@pytest.mark.asyncio
async def test_eligibility_check_invalid_json(mock_token_manager):
    """Test eligibility check with invalid JSON input"""
    tool = HCXEligibilityTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    result = await tool._run("invalid json {{{")
    
    assert result["status"] == "error"
    assert result["error_type"] == "invalid_input"
    assert "JSON" in result["message"]


@pytest.mark.asyncio
async def test_eligibility_check_timeout_with_retry(mock_token_manager):
    """Test that timeout errors trigger retry"""
    tool = HCXEligibilityTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    input_data = {
        "patient_id": "P123",
        "insurance_company": "allianz_egypt",
        "policy_number": "ALZ123456"
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        # Mock timeout exception
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )
        
        result = await tool._run(json.dumps(input_data))
        
        assert result["status"] == "error"
        assert result["error_type"] == "timeout"
        assert result["retry"] is True


@pytest.mark.asyncio
async def test_eligibility_check_auth_failure(mock_token_manager):
    """Test handling of authentication failure (401)"""
    tool = HCXEligibilityTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    input_data = {
        "patient_id": "P123",
        "insurance_company": "allianz_egypt",
        "policy_number": "ALZ123456"
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=Mock(),
                response=mock_response
            )
        )
        
        result = await tool._run(json.dumps(input_data))
        
        assert result["status"] == "error"
        assert result["error_type"] == "auth_failed"
        assert result["retry"] is True


@pytest.mark.asyncio
async def test_eligibility_check_validation_error(mock_token_manager):
    """Test handling of validation error (422)"""
    tool = HCXEligibilityTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    input_data = {
        "patient_id": "P123",
        "insurance_company": "allianz_egypt",
        "policy_number": "ALZ123456"
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "error": "Validation failed",
            "details": ["Missing required field: servicedDate"]
        }
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Validation error",
                request=Mock(),
                response=mock_response
            )
        )
        
        result = await tool._run(json.dumps(input_data))
        
        assert result["status"] == "error"
        assert result["error_type"] == "validation_error"
        assert result["retry"] is False


# ===== Pre-Authorization Tool Tests =====

@pytest.mark.asyncio
async def test_preauth_submit_success(mock_token_manager):
    """Test successful pre-authorization submission"""
    tool = HCXPreAuthTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    input_data = {
        "patient_id": "P123",
        "insurance_company": "allianz_egypt",
        "diagnoses": [
            {"code": "I21.9", "display": "Acute myocardial infarction"}
        ],
        "procedures": [
            {"code": "93458", "display": "Cardiac catheterization"}
        ],
        "justification": "Urgent cardiac intervention required"
    }
    
    mock_response = {
        "identifier": "AUTH-2025-001",
        "outcome": "approved",
        "validUntil": "2025-12-31"
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_http_response = Mock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = Mock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_http_response
        )
        
        result = await tool._run(json.dumps(input_data))
        
        assert result["status"] == "success"
        assert "authorization_number" in result
        assert result["authorization_status"] == "approved"


@pytest.mark.asyncio
async def test_preauth_server_error_triggers_retry(mock_token_manager):
    """Test that server errors (5xx) trigger retry"""
    tool = HCXPreAuthTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    input_data = {
        "patient_id": "P123",
        "insurance_company": "allianz_egypt",
        "diagnoses": [{"code": "I21.9", "display": "MI"}],
        "procedures": [{"code": "93458", "display": "Cath"}]
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 503
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Service unavailable",
                request=Mock(),
                response=mock_response
            )
        )
        
        result = await tool._run(json.dumps(input_data))
        
        assert result["status"] == "error"
        assert result["error_type"] == "server_error"
        assert result["retry"] is True


# ===== Claim Submission Tool Tests =====

@pytest.mark.asyncio
async def test_claim_submit_success(mock_token_manager):
    """Test successful claim submission"""
    tool = HCXClaimSubmitTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    # Complete FHIR Claim
    claim_data = {
        "resourceType": "Claim",
        "id": "claim-123",
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                "code": "institutional"
            }]
        },
        "use": "claim",
        "patient": {"reference": "Patient/P123"},
        "created": datetime.now().isoformat(),
        "insurer": {"reference": "Organization/allianz_egypt"},
        "provider": {"reference": "Organization/hospital-001"},
        "priority": {"coding": [{"code": "normal"}]},
        "diagnosis": [{
            "sequence": 1,
            "diagnosisCodeableConcept": {
                "coding": [{
                    "system": "http://hl7.org/fhir/sid/icd-10",
                    "code": "I21.9"
                }]
            }
        }],
        "item": [{
            "sequence": 1,
            "productOrService": {
                "coding": [{
                    "system": "http://www.ama-assn.org/go/cpt",
                    "code": "93000"
                }]
            }
        }],
        "total": {"value": 150.0, "currency": "EGP"}
    }
    
    mock_response = {
        "id": "hcx-ref-xyz789",
        "status": "received"
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_http_response = Mock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = Mock()
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_http_response
        )
        
        result = await tool._run(json.dumps(claim_data))
        
        assert result["status"] == "success"
        assert result["claim_id"] == "claim-123"
        assert result["hcx_reference"] == "hcx-ref-xyz789"
        assert "submission_date" in result


@pytest.mark.asyncio
async def test_claim_submit_invalid_fhir(mock_token_manager):
    """Test claim submission with invalid FHIR resource"""
    tool = HCXClaimSubmitTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    # Invalid claim - missing required fields
    invalid_claim = {
        "resourceType": "Claim",
        "id": "claim-invalid"
        # Missing: status, type, use, patient, provider, etc.
    }
    
    result = await tool._run(json.dumps(invalid_claim))
    
    assert result["status"] == "error"
    assert result["error_type"] == "validation_error"
    assert "Invalid FHIR claim" in result["message"]


# ===== Claim Status Tool Tests =====

@pytest.mark.asyncio
async def test_claim_status_check_success(mock_token_manager):
    """Test successful claim status check"""
    tool = HCXClaimStatusTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    mock_response = {
        "resourceType": "ClaimResponse",
        "id": "response-123",
        "status": "active",
        "outcome": "complete",
        "created": "2025-10-17T10:00:00Z",
        "disposition": "Claim approved",
        "payment": {
            "amount": {
                "value": 150.0,
                "currency": "EGP"
            }
        }
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_http_response = Mock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = Mock()
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_http_response
        )
        
        result = await tool._run("claim-123")
        
        assert result["status"] == "success"
        assert result["claim_id"] == "claim-123"
        assert result["outcome"] == "complete"
        assert result["payment_amount"] == 150.0
        assert result["disposition"] == "Claim approved"


@pytest.mark.asyncio
async def test_claim_status_pending(mock_token_manager):
    """Test claim status when still pending"""
    tool = HCXClaimStatusTool(
        hcx_url="http://test-hcx.com",
        token_manager=mock_token_manager
    )
    
    mock_response = {
        "resourceType": "Bundle",
        "entry": []  # No results yet
    }
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_http_response = Mock()
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = Mock()
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_http_response
        )
        
        result = await tool._run("claim-pending-123")
        
        assert result["status"] == "pending"
        assert result["claim_id"] == "claim-pending-123"


# ===== Integration Tests =====

@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_eligibility_workflow():
    """
    Integration test for complete eligibility workflow
    Requires HCX test environment
    """
    # Skip if HCX test environment not available
    pytest.skip("Requires HCX test environment")
    
    token_manager = TokenManager(
        hcx_url="http://localhost:8080",
        username="test_user",
        password="test_pass"
    )
    
    tool = HCXEligibilityTool(
        hcx_url="http://localhost:8080",
        token_manager=token_manager
    )
    
    input_data = {
        "patient_