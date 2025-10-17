"""
Pytest configuration and shared fixtures
Week 3-4 Implementation
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

try:
    from httpx import AsyncClient
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test_user:test_pass@localhost:5432/healthflow_test"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if SQLALCHEMY_AVAILABLE:
    @pytest.fixture(scope="session")
    async def test_engine():
        """Create test database engine"""
        engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=NullPool,
            echo=False
        )
        
        # Create all tables
        try:
            from src.services.database import Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"Warning: Could not create test tables: {e}")
        
        yield engine
        
        # Drop all tables
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        except Exception:
            pass
        
        await engine.dispose()

    @pytest.fixture
    async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
        """Create a test database session"""
        async_session = sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


if HTTPX_AVAILABLE:
    @pytest.fixture
    async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
        """Create test HTTP client"""
        try:
            from src.main import app
            from src.core.dependencies import get_db_session
            
            # Override database dependency
            async def override_get_db():
                yield db_session
            
            app.dependency_overrides[get_db_session] = override_get_db
            
            async with AsyncClient(app=app, base_url="http://test") as ac:
                yield ac
            
            app.dependency_overrides.clear()
        except ImportError:
            pytest.skip("FastAPI app not available")


@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing"""
    return {
        "id": "P12345",
        "name": {
            "given": ["John"],
            "family": "Doe"
        },
        "gender": "male",
        "birthDate": "1980-01-01",
        "identifier": [
            {
                "system": "http://hospital.example.org/patients",
                "value": "P12345"
            }
        ],
        "contact": [
            {
                "telecom": [
                    {
                        "system": "phone",
                        "value": "+1-555-123-4567",
                        "use": "mobile"
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_claim_data():
    """Sample claim data for testing"""
    return {
        "resourceType": "Claim",
        "id": "C12345",
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/claim-type",
                    "code": "institutional"
                }
            ]
        },
        "use": "claim",
        "patient": {
            "reference": "Patient/P12345"
        },
        "billablePeriod": {
            "start": "2025-01-01",
            "end": "2025-01-01"
        },
        "created": "2025-01-15",
        "provider": {
            "reference": "Organization/H001"
        },
        "priority": {
            "coding": [
                {
                    "code": "normal"
                }
            ]
        },
        "diagnosis": [
            {
                "sequence": 1,
                "diagnosisCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10",
                            "code": "E11.9",
                            "display": "Type 2 diabetes mellitus without complications"
                        }
                    ]
                }
            }
        ],
        "procedure": [
            {
                "sequence": 1,
                "procedureCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://www.ama-assn.org/go/cpt",
                            "code": "99213",
                            "display": "Office visit, established patient"
                        }
                    ]
                }
            }
        ],
        "insurance": [
            {
                "sequence": 1,
                "focal": True,
                "coverage": {
                    "reference": "Coverage/COV001"
                }
            }
        ],
        "total": {
            "value": 150.00,
            "currency": "USD"
        }
    }


@pytest.fixture
def sample_coverage_data():
    """Sample insurance coverage data"""
    return {
        "resourceType": "Coverage",
        "id": "COV001",
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "HIP",
                    "display": "health insurance plan policy"
                }
            ]
        },
        "policyHolder": {
            "reference": "Patient/P12345"
        },
        "subscriber": {
            "reference": "Patient/P12345"
        },
        "beneficiary": {
            "reference": "Patient/P12345"
        },
        "relationship": {
            "coding": [
                {
                    "code": "self"
                }
            ]
        },
        "period": {
            "start": "2025-01-01",
            "end": "2025-12-31"
        },
        "payor": [
            {
                "reference": "Organization/Allianz"
            }
        ],
        "class": [
            {
                "type": {
                    "coding": [
                        {
                            "code": "group"
                        }
                    ]
                },
                "value": "GRP001"
            }
        ]
    }


@pytest.fixture
def sample_icd10_codes():
    """Sample ICD-10 codes for testing"""
    return [
        {
            "code": "E11.9",
            "description": "Type 2 diabetes mellitus without complications",
            "category": "Endocrine",
            "subcategory": "Diabetes",
            "is_billable": True
        },
        {
            "code": "I10",
            "description": "Essential (primary) hypertension",
            "category": "Circulatory",
            "subcategory": "Hypertensive diseases",
            "is_billable": True
        },
        {
            "code": "J44.0",
            "description": "COPD with acute lower respiratory infection",
            "category": "Respiratory",
            "subcategory": "COPD",
            "is_billable": True
        }
    ]


@pytest.fixture
def sample_cpt_codes():
    """Sample CPT codes for testing"""
    return [
        {
            "code": "99213",
            "description": "Office visit, established patient, 20-29 minutes",
            "category": "E&M",
            "modifier_allowed": True,
            "base_rate": 150.00,
            "rvu": 1.5
        },
        {
            "code": "99214",
            "description": "Office visit, established patient, 30-39 minutes",
            "category": "E&M",
            "modifier_allowed": True,
            "base_rate": 220.00,
            "rvu": 2.5
        },
        {
            "code": "80053",
            "description": "Comprehensive metabolic panel",
            "category": "Laboratory",
            "modifier_allowed": True,
            "base_rate": 45.00,
            "rvu": 0.5
        }
    ]


@pytest.fixture
def mock_hcx_response():
    """Mock HCX API response"""
    return {
        "apiCallId": "abc123",
        "correlationId": "corr456",
        "timestamp": "2025-10-17T12:00:00Z",
        "status": "response.complete",
        "response": {
            "eligible": True,
            "copay": 50.00,
            "deductible_remaining": 500.00,
            "coverage_status": "active"
        }
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    class MockRedis:
        def __init__(self):
            self.store = {}
        
        async def get(self, key):
            return self.store.get(key)
        
        async def set(self, key, value, ex=None):
            self.store[key] = value
            return True
        
        async def delete(self, key):
            if key in self.store:
                del self.store[key]
            return True
        
        async def close(self):
            pass
    
    return MockRedis()

