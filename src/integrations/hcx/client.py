"""
HCX API Client with Retry Logic and Error Handling
Week 5-6 Implementation
"""
import asyncio
import logging
from typing import Dict, Any, Optional
import httpx
from datetime import datetime
import uuid

from .config import hcx_config
from .auth import auth_manager

logger = logging.getLogger(__name__)


class HCXClient:
    """
    HCX API Client for Egyptian HCX Platform
    Handles eligibility checks, pre-authorization, and claims submission
    """
    
    def __init__(self):
        if not hcx_config:
            raise ValueError("HCX configuration not available")
        if not auth_manager:
            raise ValueError("HCX auth manager not available")
        
        self.config = hcx_config
        self.auth = auth_manager
        self._rate_limiter = asyncio.Semaphore(self.config.rate_limit_per_minute)
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP request to HCX API with retry logic
        """
        url = f"{self.config.base_url}/{endpoint}"
        
        # Get fresh access token
        token = await self.auth.get_access_token()
        headers = self.auth.get_auth_headers()
        
        try:
            async with self._rate_limiter:
                async with httpx.AsyncClient() as client:
                    if method.upper() == "GET":
                        response = await client.get(
                            url,
                            headers=headers,
                            timeout=self.config.request_timeout
                        )
                    else:
                        response = await client.post(
                            url,
                            json=payload,
                            headers=headers,
                            timeout=self.config.request_timeout
                        )
                    
                    response.raise_for_status()
                    return response.json()
        
        except httpx.HTTPStatusError as e:
            # Handle specific HTTP errors
            status_code = e.response.status_code
            
            # Retry on 5xx errors or 429 (rate limit)
            if (status_code >= 500 or status_code == 429) and retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (2 ** retry_count)  # Exponential backoff
                logger.warning(f"Request failed with {status_code}, retrying in {delay}s (attempt {retry_count + 1}/{self.config.max_retries})")
                await asyncio.sleep(delay)
                return await self._make_request(method, endpoint, payload, retry_count + 1)
            
            # Log and raise for other errors
            logger.error(f"HCX API error: {status_code} - {e.response.text}")
            raise ValueError(f"HCX API error: {status_code} - {e.response.text}")
        
        except httpx.TimeoutException:
            # Retry on timeout
            if retry_count < self.config.max_retries:
                delay = self.config.retry_delay * (2 ** retry_count)
                logger.warning(f"Request timeout, retrying in {delay}s (attempt {retry_count + 1}/{self.config.max_retries})")
                await asyncio.sleep(delay)
                return await self._make_request(method, endpoint, payload, retry_count + 1)
            
            logger.error("HCX API timeout after max retries")
            raise ValueError("HCX API timeout")
        
        except Exception as e:
            logger.error(f"HCX API request failed: {e}")
            raise
    
    async def check_eligibility(
        self,
        patient_id: str,
        insurance_id: str,
        service_type: str = "OPD",
        provider_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check patient eligibility with insurance
        
        Args:
            patient_id: Patient identifier
            insurance_id: Insurance policy number
            service_type: Type of service (OPD, IPD, Emergency)
            provider_id: Healthcare provider identifier
        
        Returns:
            Eligibility response with coverage details
        """
        correlation_id = str(uuid.uuid4())
        
        payload = {
            "apiCallId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "coverage/eligibility/check",
            "sender": {
                "participantCode": self.config.participant_code,
                "role": "provider"
            },
            "payload": {
                "patientId": patient_id,
                "insuranceId": insurance_id,
                "serviceType": service_type,
                "providerId": provider_id or self.config.participant_code
            }
        }
        
        logger.info(f"🔍 Checking eligibility for patient {patient_id}, correlation_id: {correlation_id}")
        
        try:
            response = await self._make_request("POST", "coverageeligibility/check", payload)
            logger.info(f"✅ Eligibility check successful: {response.get('eligible', False)}")
            return response
        except Exception as e:
            logger.error(f"❌ Eligibility check failed: {e}")
            raise
    
    async def submit_preauth(
        self,
        patient_id: str,
        insurance_id: str,
        diagnosis_codes: list,
        procedure_codes: list,
        estimated_amount: float,
        provider_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit pre-authorization request
        
        Args:
            patient_id: Patient identifier
            insurance_id: Insurance policy number
            diagnosis_codes: List of ICD-10 diagnosis codes
            procedure_codes: List of CPT procedure codes
            estimated_amount: Estimated claim amount
            provider_id: Healthcare provider identifier
        
        Returns:
            Pre-authorization response
        """
        correlation_id = str(uuid.uuid4())
        
        payload = {
            "apiCallId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "preauth/submit",
            "sender": {
                "participantCode": self.config.participant_code,
                "role": "provider"
            },
            "payload": {
                "patientId": patient_id,
                "insuranceId": insurance_id,
                "diagnosisCodes": diagnosis_codes,
                "procedureCodes": procedure_codes,
                "estimatedAmount": estimated_amount,
                "providerId": provider_id or self.config.participant_code,
                "priority": "normal"
            }
        }
        
        logger.info(f"📝 Submitting pre-authorization for patient {patient_id}, correlation_id: {correlation_id}")
        
        try:
            response = await self._make_request("POST", "preauth/submit", payload)
            logger.info(f"✅ Pre-authorization submitted: {response.get('status', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"❌ Pre-authorization submission failed: {e}")
            raise
    
    async def submit_claim(
        self,
        claim_id: str,
        patient_id: str,
        insurance_id: str,
        diagnosis_codes: list,
        procedure_codes: list,
        total_amount: float,
        preauth_ref: Optional[str] = None,
        provider_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit insurance claim
        
        Args:
            claim_id: Unique claim identifier
            patient_id: Patient identifier
            insurance_id: Insurance policy number
            diagnosis_codes: List of ICD-10 diagnosis codes
            procedure_codes: List of CPT procedure codes
            total_amount: Total claim amount
            preauth_ref: Pre-authorization reference (if applicable)
            provider_id: Healthcare provider identifier
        
        Returns:
            Claim submission response
        """
        correlation_id = str(uuid.uuid4())
        
        payload = {
            "apiCallId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "claim/submit",
            "sender": {
                "participantCode": self.config.participant_code,
                "role": "provider"
            },
            "payload": {
                "claimId": claim_id,
                "patientId": patient_id,
                "insuranceId": insurance_id,
                "diagnosisCodes": diagnosis_codes,
                "procedureCodes": procedure_codes,
                "totalAmount": total_amount,
                "preauthRef": preauth_ref,
                "providerId": provider_id or self.config.participant_code,
                "billDate": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        logger.info(f"💰 Submitting claim {claim_id} for patient {patient_id}, correlation_id: {correlation_id}")
        
        try:
            response = await self._make_request("POST", "claim/submit", payload)
            logger.info(f"✅ Claim submitted: {response.get('status', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"❌ Claim submission failed: {e}")
            raise
    
    async def check_claim_status(self, claim_id: str) -> Dict[str, Any]:
        """
        Check status of submitted claim
        
        Args:
            claim_id: Claim identifier
        
        Returns:
            Claim status response
        """
        correlation_id = str(uuid.uuid4())
        
        payload = {
            "apiCallId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "claim/status",
            "sender": {
                "participantCode": self.config.participant_code,
                "role": "provider"
            },
            "payload": {
                "claimId": claim_id
            }
        }
        
        logger.info(f"🔍 Checking status for claim {claim_id}, correlation_id: {correlation_id}")
        
        try:
            response = await self._make_request("POST", "claim/status", payload)
            status = response.get('status', 'unknown')
            logger.info(f"✅ Claim status: {status}")
            return response
        except Exception as e:
            logger.error(f"❌ Claim status check failed: {e}")
            raise
    
    async def get_communication(self, communication_id: str) -> Dict[str, Any]:
        """
        Get communication/response from HCX
        
        Args:
            communication_id: Communication identifier
        
        Returns:
            Communication details
        """
        try:
            response = await self._make_request("GET", f"communication/{communication_id}")
            logger.info(f"✅ Communication retrieved: {communication_id}")
            return response
        except Exception as e:
            logger.error(f"❌ Communication retrieval failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check HCX API health status
        
        Returns:
            Health status response
        """
        try:
            response = await self._make_request("GET", "health")
            logger.info(f"✅ HCX health check: {response.get('status', 'unknown')}")
            return response
        except Exception as e:
            logger.error(f"❌ HCX health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}


# Global instance
hcx_client = HCXClient() if (hcx_config and auth_manager) else None

