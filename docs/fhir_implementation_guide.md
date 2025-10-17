# FHIR Implementation Guide

**Objective:** Fix incomplete FHIR resource generation by using the official `fhir.resources` library to create complete, valid FHIR R4 objects that comply with HCX specifications.

---

## 1. The Problem: Incomplete FHIR Resources

The current implementation creates FHIR resources as simple Python dictionaries. These resources are missing many required fields and do not conform to the strict FHIR R4 standard, which will cause them to be **rejected** by the HCX gateway.

**Example of incorrect, incomplete resource:**
```python
fhir_request = {
    "resourceType": "CoverageEligibilityRequest",
    "status": "active",
    "patient": {"reference": f"Patient/{data['patient_id']}"},
    # This is missing id, meta, identifier, servicedDate, insurer, etc.
}
```

## 2. The Solution: Use `fhir.resources` Library

The correct approach is to use the `fhir.resources` library, which provides Pydantic-based models for all FHIR R4 resources. This library ensures that all created objects are valid and complete according to the FHIR specification.

### Step 1: Install the Library

```bash
pip install fhir.resources
```

### Step 2: Update `src/tools/hcx_tools.py`

Rewrite the HCX tools to use the `fhir.resources` models. Here is the corrected implementation for `HCXEligibilityTool`:

```python
# src/tools/hcx_tools.py

import httpx
import json
import uuid
from typing import Dict, Any
from datetime import datetime
from praisonaiagents.tools import Tool

# Import FHIR resources
from fhir.resources.coverageeligibilityrequest import CoverageEligibilityRequest
from fhir.resources.identifier import Identifier
from fhir.resources.reference import Reference
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding

class HCXEligibilityTool(Tool):
    """Tool for checking insurance eligibility via HCX with complete FHIR resources"""
    
    name = "hcx_eligibility_check"
    description = """Check patient insurance eligibility through HCX platform.
    Input should be JSON with: patient_id, insurance_company, policy_number, service_date"""
    
    def __init__(self, hcx_url: str, auth_token: str):
        super().__init__()
        self.hcx_url = hcx_url
        self.auth_token = auth_token
    
    async def _run(self, query: str) -> Dict[str, Any]:
        """Execute eligibility check using valid FHIR R4 model"""
        try:
            data = json.loads(query)
            
            # Create a complete and valid FHIR CoverageEligibilityRequest
            fhir_request = CoverageEligibilityRequest(
                resourceType="CoverageEligibilityRequest",
                id=str(uuid.uuid4()),
                meta={
                    "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/CoverageEligibilityRequest"]
                },
                identifier=[
                    Identifier(
                        system="http://hospital.org/eligibility-requests",
                        value=f"ELG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    )
                ],
                status="active",
                purpose=["benefits", "validation"],
                patient=Reference(reference=f"Patient/{data['patient_id']}"),
                servicedDate=data.get('service_date', datetime.now().date().isoformat()),
                created=datetime.now().isoformat(),
                insurer=Reference(reference=f"Organization/{data['insurance_company']}"),
                provider=Reference(reference="Organization/hospital-001"), # Should be configurable
                insurance=[{
                    "coverage": Reference(reference=f"Coverage/{data['policy_number']}")
                }]
            )

            # Validate the created resource before sending
            validated_request_json = fhir_request.json()

            # Call HCX API asynchronously
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.hcx_url}/coverageeligibility/check",
                    content=validated_request_json,
                    headers={
                        "Authorization": f"Bearer {self.auth_token}",
                        "Content-Type": "application/fhir+json"
                    },
                    timeout=30
                )
            
            response.raise_for_status()
            result = response.json()
            
            # (Further logic to parse the FHIR response safely)
            return {
                "status": "success",
                "message": "Eligibility check submitted successfully.",
                "fhir_request": json.loads(validated_request_json),
                "raw_response": result
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to check eligibility"
            }

```

### Key Changes:

1.  **Imported FHIR Models:** The code now imports specific FHIR resource models like `CoverageEligibilityRequest`, `Identifier`, and `Reference`.
2.  **Created a Valid FHIR Object:** Instead of a dictionary, `CoverageEligibilityRequest(...)` is used to create a strongly-typed object.
3.  **Added Required Fields:** The new implementation includes `id`, `meta` (with HCX profile), `identifier`, `servicedDate`, `insurer`, and `provider`.
4.  **Used `Reference` Type:** Patient, insurer, and provider are now correctly represented using the `Reference` model.
5.  **JSON Serialization:** The `fhir_request.json()` method is used to get a valid JSON representation of the FHIR object.
6.  **Asynchronous API Call:** The `httpx` call is now properly `await`ed within an `async` function, preventing it from blocking the application.

## 3. How to Apply This Fix

1.  **Install the `fhir.resources` library:** `pip install fhir.resources`
2.  **Update your `src/tools/hcx_tools.py` file** by replacing the `HCXEligibilityTool` with the code above.
3.  **Apply the same pattern** to the other tools (`HCXPreAuthTool`, `HCXClaimSubmitTool`) to ensure all outgoing FHIR resources are complete and valid.

By following this guide, you will ensure that your application generates FHIR resources that are compliant with both the FHIR R4 standard and the specific requirements of the HCX platform, significantly increasing your claim acceptance rate and reducing rejections due to validation errors.

