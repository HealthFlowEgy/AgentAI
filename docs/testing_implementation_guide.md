# Testing Implementation Guide

**Objective:** Build a comprehensive testing suite to ensure the reliability, correctness, and performance of the Healthcare RCM Agent System. This guide covers unit, integration, and end-to-end (E2E) testing.

---

## 1. The Problem: No Testing Suite

The current implementation has **zero automated tests**. This means:
- There is no way to verify that the code works as expected.
- Refactoring or adding new features is extremely risky and likely to introduce bugs.
- It is impossible to guarantee compliance with HCX specifications.
- The system is not production-ready.

## 2. The Solution: A Multi-Layered Testing Strategy

We will implement a three-layered testing strategy using `pytest`:

1.  **Unit Tests:** To test individual components (like tools and services) in isolation.
2.  **Integration Tests:** To test the interaction between components (e.g., API endpoints and the database).
3.  **End-to-End (E2E) Tests:** To test the complete RCM workflow from start to finish.

### Step 1: Install Testing Libraries

```bash
pip install pytest pytest-asyncio respx
```

-   `pytest`: The testing framework.
-   `pytest-asyncio`: For testing asynchronous code.
-   `respx`: To mock HTTP requests made by `httpx`, so we can test HCX integration without making real API calls.

### Step 2: Create Unit Tests

Unit tests should be placed in a `tests/unit` directory. Let's create a unit test for the `HCXEligibilityTool`.

```python
# tests/unit/test_hcx_tools.py

import pytest
import json
import respx
from httpx import Response

from src.tools.hcx_tools import HCXEligibilityTool

@pytest.mark.asyncio
@respx.mock
async def test_hcx_eligibility_tool_success():
    """Test the HCXEligibilityTool for a successful eligibility check."""
    # Arrange: Mock the HCX API endpoint
    hcx_api_route = respx.post("http://testhost/coverageeligibility/check").mock(
        return_value=Response(200, json={
            "resourceType": "CoverageEligibilityResponse",
            "outcome": "complete",
            "insurance": [{"inforce": True}]
        })
    )

    # Instantiate the tool
    tool = HCXEligibilityTool(hcx_url="http://testhost", auth_token="fake-token")
    
    # Define the input query
    query = json.dumps({
        "patient_id": "P123",
        "insurance_company": "INS456",
        "policy_number": "POL789",
        "service_date": "2025-10-17"
    })

    # Act: Run the tool
    result = await tool._run(query)

    # Assert: Check the results
    assert hcx_api_route.called, "The HCX API should have been called."
    assert result["status"] == "success"
    assert "fhir_request" in result
    assert result["raw_response"]["outcome"] == "complete"

@pytest.mark.asyncio
@respx.mock
async def test_hcx_eligibility_tool_api_error():
    """Test the HCXEligibilityTool when the HCX API returns an error."""
    # Arrange: Mock the HCX API to return a 500 error
    respx.post("http://testhost/coverageeligibility/check").mock(
        return_value=Response(500, json={"error": "Internal Server Error"})
    )

    tool = HCXEligibilityTool(hcx_url="http://testhost", auth_token="fake-token")
    query = json.dumps({"patient_id": "P123"})

    # Act: Run the tool
    result = await tool._run(query)

    # Assert: Check that the error is handled gracefully
    assert result["status"] == "error"
    assert "500" in result["error"]

```

### Step 3: Create Integration Tests

Integration tests go in `tests/integration`. These tests should use a **separate test database** to avoid corrupting production data.

```python
# tests/integration/test_claims_api.py

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

from api.main import app # Import your FastAPI app
from src.services.database import get_db, init_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Test Database Setup ---
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = testing_session_local()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# --- Tests ---

def test_submit_claim_success():
    """Test successful claim submission through the API."""
    # Arrange: Define a valid claim request
    claim_request = {
        "encounter_id": "ENC-INT-001",
        "patient_id": "PAT-INT-001",
        # ... other required fields
    }

    # Act: Call the API endpoint
    response = client.post("/api/v1/claims/submit", json=claim_request)

    # Assert: Check the response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["claim_id"] is not None
    assert "Workflow started successfully" in data["message"]

def test_submit_claim_invalid_data():
    """Test claim submission with missing required fields."""
    # Arrange: Invalid request with missing patient_id
    invalid_request = {"encounter_id": "ENC-INT-002"}

    # Act: Call the API
    response = client.post("/api/v1/claims/submit", json=invalid_request)

    # Assert: Expect a 422 Unprocessable Entity error
    assert response.status_code == 422

```

### Step 4: Create End-to-End (E2E) Tests

E2E tests simulate a real user workflow and should be in `tests/e2e`. These tests will run against a fully running application, including a test database and mocked external services.

```python
# tests/e2e/test_full_rcm_workflow.py

import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_rcm_workflow_happy_path():
    """Test the complete RCM workflow from registration to claim status check."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: Submit a new encounter
        encounter_data = {
            "encounter_id": "E2E-001",
            "patient_id": "PAT-E2E-001",
            "insurance_company": "allianz_egypt",
            # ... other fields
        }
        response = await client.post("/api/v1/claims/submit", json=encounter_data)
        assert response.status_code == 200
        claim_id = response.json()["claim_id"]

        # Step 2: Wait for asynchronous processing to complete
        # (In a real test, you might poll a status endpoint)
        await asyncio.sleep(10) 

        # Step 3: Check the final status of the claim
        response = await client.get(f"/api/v1/claims/{claim_id}/status")
        assert response.status_code == 200
        status_data = response.json()

        # Assert final state
        assert status_data["claim_id"] == claim_id
        assert status_data["status"] == "accepted" # Or "rejected", depending on the test case
        assert status_data["hcx_reference"] is not None

```

## 3. How to Run the Tests

1.  **Create the directory structure:**

    ```bash
    mkdir -p tests/unit tests/integration tests/e2e
    ```

2.  **Add the test files** as shown above.

3.  **Run all tests** from the project root directory:

    ```bash
    pytest
    ```

4.  **Run tests for a specific file:**

    ```bash
    pytest tests/unit/test_hcx_tools.py
    ```

## 4. Recommendations for Coverage

-   **Aim for 80%+ unit test coverage.** Every tool, service, and utility function should have unit tests.
-   **Write integration tests for every API endpoint.**
-   **Create E2E tests for the most critical workflows:**
    -   Successful claim submission ("happy path").
    -   Claim submission that gets denied.
    -   Eligibility check for an ineligible patient.
    -   Workflow with a required pre-authorization.

By implementing this testing suite, you will build confidence in your codebase, reduce bugs, and ensure the system is ready for the complexities of a production healthcare environment.

