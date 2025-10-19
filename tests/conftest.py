"""
Pytest configuration and fixtures for HealthFlow RCM tests
Provides database, async session, test data, and mock fixtures
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient
import uuid

from src.core.config import settings
from src.models.base import Base
from src.models.patient import Patient
from src.models.claim import Claim, ClaimItem, ClaimDiagnosis
from src.models.coverage import Coverage
from src.models.medical_codes import ICD10Code, CPTCode
from src.api.main import app

# Test database URL
TEST_DATABASE_URL = settings.database_url.replace(
    'healthflow_prod',
    'healthflow_test'
).replace('postgresql://', 'postgresql+asyncpg://')


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests"""
    SessionLocal = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def sample_patient(db_session: AsyncSession) -> Patient:
    """Create sample patient for testing"""
    patient = Patient(
        id=str(uuid.uuid4()),
        national_id="29512011234567",
        first_name="Ahmed",
        last_name="Mohamed",
        date_of_birth=date(1995, 12, 1),
        gender="male",
        phone="+201234567890",
        email="ahmed.mohamed@example.com",
        address="123 Main St, Cairo, Egypt",
        city="Cairo",
        governorate="Cairo",
        postal_code="11511"
    )
    
    db_session.add(patient)
    await db_session.commit()
    await db_session.refresh(patient)
    
    return patient


@pytest_asyncio.fixture
async def sample_coverage(db_session: AsyncSession, sample_patient: Patient) -> Coverage:
    """Create sample insurance coverage"""
    coverage = Coverage(
        id=str(uuid.uuid4()),
        patient_id=sample_patient.id,
        subscriber_id="SUB123456",
        payer_id="PAYER001",
        payer_name="Egyptian National Health Insurance",
        policy_number="POL-2025-001234",
        group_number="GRP-001",
        status="active",
        coverage_start_date=date(2025, 1, 1),
        coverage_end_date=date(2025, 12, 31),
        copay_amount=50.0,
        deductible_amount=500.0,
        deductible_met=200.0,
        out_of_pocket_max=5000.0,
        out_of_pocket_met=200.0
    )
    
    db_session.add(coverage)
    await db_session.commit()
    await db_session.refresh(coverage)
    
    return coverage


@pytest_asyncio.fixture
async def sample_icd10_codes(db_session: AsyncSession) -> list[ICD10Code]:
    """Create sample ICD-10 codes"""
    codes = [
        ICD10Code(
            code="E11.9",
            description="Type 2 diabetes mellitus without complications",
            category="Endocrine",
            subcategory="Diabetes",
            billable=True,
            valid_for_coding=True,
            effective_date=date.today()
        ),
        ICD10Code(
            code="I10",
            description="Essential (primary) hypertension",
            category="Circulatory",
            subcategory="Hypertension",
            billable=True,
            valid_for_coding=True,
            effective_date=date.today()
        ),
        ICD10Code(
            code="J45.909",
            description="Unspecified asthma, uncomplicated",
            category="Respiratory",
            subcategory="Asthma",
            billable=True,
            valid_for_coding=True,
            effective_date=date.today()
        ),
    ]
    
    for code in codes:
        db_session.add(code)
    
    await db_session.commit()
    
    return codes


@pytest_asyncio.fixture
async def sample_cpt_codes(db_session: AsyncSession) -> list[CPTCode]:
    """Create sample CPT codes"""
    codes = [
        CPTCode(
            code="99213",
            description="Office/outpatient visit, established patient, 20-29 minutes",
            category="E/M",
            rvu=1.92,
            facility_rvu=1.92,
            non_facility_rvu=1.92,
            effective_date=date.today()
        ),
        CPTCode(
            code="99214",
            description="Office/outpatient visit, established patient, 30-39 minutes",
            category="E/M",
            rvu=2.80,
            facility_rvu=2.80,
            non_facility_rvu=2.80,
            effective_date=date.today()
        ),
        CPTCode(
            code="82947",
            description="Glucose; quantitative, blood",
            category="Laboratory",
            rvu=0.15,
            facility_rvu=0.15,
            non_facility_rvu=0.15,
            effective_date=date.today()
        ),
    ]
    
    for code in codes:
        db_session.add(code)
    
    await db_session.commit()
    
    return codes


@pytest_asyncio.fixture
async def sample_claim(
    db_session: AsyncSession,
    sample_patient: Patient,
    sample_coverage: Coverage,
    sample_icd10_codes: list[ICD10Code],
    sample_cpt_codes: list[CPTCode]
) -> Claim:
    """Create sample claim"""
    claim = Claim(
        id=str(uuid.uuid4()),
        patient_id=sample_patient.id,
        coverage_id=sample_coverage.id,
        provider_id="PROV-001",
        facility_id="FAC-001",
        claim_number=f"CLM-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        claim_type="professional",
        service_date=date.today(),
        total_charge_amount=500.0,
        status="draft",
        priority="normal"
    )
    
    db_session.add(claim)
    await db_session.flush()
    
    # Add diagnosis
    diagnosis = ClaimDiagnosis(
        claim_id=claim.id,
        diagnosis_code=sample_icd10_codes[0].code,
        diagnosis_type="primary",
        sequence=1
    )
    db_session.add(diagnosis)
    
    # Add claim items
    for idx, cpt_code in enumerate(sample_cpt_codes[:2], 1):
        item = ClaimItem(
            claim_id=claim.id,
            sequence=idx,
            procedure_code=cpt_code.code,
            procedure_description=cpt_code.description,
            service_date=date.today(),
            quantity=1.0,
            unit_price=200.0,
            total_price=200.0
        )
        db_session.add(item)
    
    await db_session.commit()
    await db_session.refresh(claim)
    
    return claim


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_hcx_eligibility_response():
    """Mock HCX eligibility check response"""
    return {
        "resourceType": "CoverageEligibilityResponse",
        "id": str(uuid.uuid4()),
        "status": "active",
        "purpose": ["validation"],
        "patient": {
            "reference": "Patient/test-patient-123"
        },
        "created": datetime.now().isoformat(),
        "insurer": {
            "reference": "Organization/test-payer-001"
        },
        "outcome": "complete",
        "insurance": [{
            "coverage": {
                "reference": "Coverage/test-coverage-123"
            },
            "inforce": True,
            "benefitPeriod": {
                "start": "2025-01-01",
                "end": "2025-12-31"
            },
            "item": [{
                "category": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/ex-benefitcategory",
                        "code": "30",
                        "display": "Health Benefit Plan Coverage"
                    }]
                },
                "benefit": [{
                    "type": {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/benefit-type",
                            "code": "benefit"
                        }]
                    },
                    "allowedMoney": {
                        "value": 1000000,
                        "currency": "EGP"
                    }
                }]
            }]
        }]
    }


@pytest.fixture
def mock_hcx_claim_response():
    """Mock HCX claim submission response"""
    return {
        "resourceType": "ClaimResponse",
        "id": str(uuid.uuid4()),
        "status": "active",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                "code": "professional"
            }]
        },
        "use": "claim",
        "patient": {
            "reference": "Patient/test-patient-123"
        },
        "created": datetime.now().isoformat(),
        "insurer": {
            "reference": "Organization/test-payer-001"
        },
        "outcome": "complete",
        "item": [{
            "itemSequence": 1,
            "adjudication": [{
                "category": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/adjudication",
                        "code": "submitted"
                    }]
                },
                "amount": {
                    "value": 200.0,
                    "currency": "EGP"
                }
            }, {
                "category": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/adjudication",
                        "code": "benefit"
                    }]
                },
                "amount": {
                    "value": 180.0,
                    "currency": "EGP"
                }
            }]
        }],
        "total": [{
            "category": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/adjudication",
                    "code": "submitted"
                }]
            },
            "amount": {
                "value": 500.0,
                "currency": "EGP"
            }
        }, {
            "category": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/adjudication",
                    "code": "benefit"
                }]
            },
            "amount": {
                "value": 450.0,
                "currency": "EGP"
            }
        }]
    }


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response"""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model": "gpt-4",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a test response from the AI agent."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

@pytest.fixture
def assert_valid_fhir_resource():
    """Helper to validate FHIR resources"""
    def _validate(resource_dict: dict, resource_type: str):
        assert "resourceType" in resource_dict
        assert resource_dict["resourceType"] == resource_type
        assert "id" in resource_dict or resource_dict.get("status") == "draft"
        return True
    return _validate


@pytest.fixture
def create_test_claim_payload():
    """Helper to create test claim payload"""
    def _create(
        patient_id: str,
        coverage_id: str,
        total_amount: float = 500.0
    ) -> dict:
        return {
            "patient_id": patient_id,
            "coverage_id": coverage_id,
            "provider_id": "PROV-001",
            "facility_id": "FAC-001",
            "claim_type": "professional",
            "service_date": date.today().isoformat(),
            "total_charge_amount": total_amount,
            "diagnoses": [{
                "code": "E11.9",
                "type": "primary",
                "sequence": 1
            }],
            "items": [{
                "sequence": 1,
                "procedure_code": "99213",
                "quantity": 1,
                "unit_price": total_amount
            }]
        }
    return _create
