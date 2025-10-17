_# Missing Agents Implementation Guide

**Objective:** Implement the critical missing backend agents required to complete the RCM workflow: the `DenialManagementAgent` and the `PaymentPostingAgent`.

---

## 1. The Problem: Incomplete RCM Workflow

The current system stops after claim submission. A real-world RCM cycle only ends when the claim is paid or fully resolved. The following backend processes are missing:

1.  **Denial Management:** Analyzing rejected claims, determining the root cause, and managing the appeals process.
2.  **Payment Posting:** Receiving remittance advice, posting payments to patient accounts, and reconciling discrepancies.

## 2. The Solution: Implement Backend Agents

We will create two new agents and their associated tools to handle these post-submission workflows.

### Step 1: Implement the Denial Management Agent

This agent will be responsible for handling claims that are rejected by the payer.

#### A. Create the Denial Analysis Tool

First, create a new tool that can analyze a denial reason and suggest a corrective action.

```python
# src/tools/denial_tools.py

from praisonaiagents.tools import Tool
from typing import Dict, Any
import json

class DenialAnalysisTool(Tool):
    """Tool for analyzing claim denial reasons and suggesting next steps."""
    
    name = "denial_analysis_tool"
    description = """Analyzes a claim denial based on the reason code and text.
    Input should be JSON with: denial_code, denial_reason, claim_data"""

    def _run(self, query: str) -> Dict[str, Any]:
        """Analyzes the denial and suggests a course of action."""
        data = json.loads(query)
        denial_code = data.get("denial_code")
        denial_reason = data.get("denial_reason", "").lower()

        suggestion = {
            "next_step": "manual_review",
            "confidence": 0.6,
            "appeal_strategy": "Provide additional documentation."
        }

        if "eligibility" in denial_reason or "coverage terminated" in denial_reason:
            suggestion.update({
                "next_step": "correct_and_resubmit",
                "confidence": 0.95,
                "appeal_strategy": "Verify patient coverage for the date of service and update the claim with correct policy information. Resubmit as a corrected claim."
            })
        elif "medical necessity" in denial_reason or "not medically necessary" in denial_reason:
            suggestion.update({
                "next_step": "appeal_with_medical_records",
                "confidence": 0.9,
                "appeal_strategy": "Submit an appeal with the physician's notes, relevant test results, and a letter of medical necessity explaining why the service was critical for the patient's diagnosis and treatment."
            })
        elif "coding error" in denial_reason or "invalid code" in denial_reason:
            suggestion.update({
                "next_step": "recode_and_resubmit",
                "confidence": 0.98,
                "appeal_strategy": "Review the clinical documentation to verify the correct ICD-10 and CPT codes. Correct any coding mistakes and resubmit the claim."
            })
        
        return suggestion

```

#### B. Create the Denial Management Agent

Now, create the agent that uses this tool.

```python
# src/agents/backend_agents.py

from praisonaiagents import Agent
from typing import List

from src.tools.denial_tools import DenialAnalysisTool

def create_denial_management_agent() -> Agent:
    """Creates the agent responsible for handling claim denials."""
    return Agent(
        name="DenialManagementAgent",
        role="Denial Management Specialist",
        goal="Analyze every denied claim, identify the root cause, and initiate the appeal or correction process to recover revenue.",
        backstory=(
            "An expert in navigating the complex world of insurance denials. With over a decade of experience, this agent has a " 
            "90% success rate in overturning denials. It is analytical, persistent, and an expert in payer-specific appeal requirements."
        ),
        tools=[DenialAnalysisTool()],
        verbose=True,
        memory=True # Remembers which appeal strategies work best for each payer
    )

```

### Step 2: Implement the Payment Posting Agent

This agent will handle the final step of the RCM cycle: posting payments.

#### A. Create the Payment Posting Tool

This tool will simulate receiving an Electronic Remittance Advice (ERA) and posting the payment to the system.

```python
# src/tools/payment_tools.py

from praisonaiagents.tools import Tool
from typing import Dict, Any
import json

class PaymentPostingTool(Tool):
    """Tool for posting payments from remittance advice to a claim."""
    
    name = "payment_posting_tool"
    description = """Posts a payment to a claim and calculates the contractual adjustment.
    Input should be JSON with: claim_id, paid_amount, allowed_amount, charge_amount"""

    def _run(self, query: str) -> Dict[str, Any]:
        """Posts the payment and returns the final account balance."""
        data = json.loads(query)
        claim_id = data.get("claim_id")
        paid_amount = float(data.get("paid_amount", 0))
        allowed_amount = float(data.get("allowed_amount", 0))
        charge_amount = float(data.get("charge_amount", 0))

        contractual_adjustment = charge_amount - allowed_amount
        patient_responsibility = allowed_amount - paid_amount

        # In a real system, this would update the database.
        print(f"DATABASE UPDATE for Claim {claim_id}:")
        print(f"  - Actual Payment: {paid_amount}")
        print(f"  - Contractual Adjustment: {contractual_adjustment}")
        print(f"  - Patient Responsibility: {patient_responsibility}")

        return {
            "status": "posted",
            "claim_id": claim_id,
            "patient_responsibility": round(patient_responsibility, 2),
            "account_balance": round(patient_responsibility, 2)
        }

```

#### B. Create the Payment Posting Agent

```python
# src/agents/backend_agents.py (continued)

from src.tools.payment_tools import PaymentPostingTool

def create_payment_posting_agent() -> Agent:
    """Creates the agent responsible for posting payments."""
    return Agent(
        name="PaymentPostingAgent",
        role="Payment Posting Specialist",
        goal="Accurately and efficiently post all payments from payers, identify variances, and balance patient accounts.",
        backstory=(
            "A meticulous and detail-oriented specialist responsible for the final financial reconciliation of claims. " 
            "This agent ensures that every dollar is accounted for, handling electronic remittance advice (ERA) with 99.9% accuracy."
        ),
        tools=[PaymentPostingTool()],
        verbose=True
    )

```

## 3. How to Integrate the New Agents

These agents would be triggered by events from the HCX platform or your internal system.

1.  **Triggering the Denial Agent:** When the `HCXClaimStatusTool` receives a `ClaimResponse` with an `outcome` of "error" or "fail", it should trigger a new task for the `DenialManagementAgent`.

2.  **Triggering the Payment Agent:** When the `HCXClaimStatusTool` receives a `ClaimResponse` with an `outcome` of "complete" and a payment amount, it should trigger a new task for the `PaymentPostingAgent`.

### Example Workflow Update

Your main workflow orchestrator would need a new step:

```python
# In your main workflow logic

# ... after claim submission and status check ...
claim_status_result = await claim_status_task.execute()

if claim_status_result.get("outcome") == "fail":
    denial_task = Task(
        description=f"Analyze denial for claim {claim_id} and determine next steps. Denial reason: {claim_status_result.get('disposition')}",
        expected_output="A clear action plan for appealing or correcting the denied claim.",
        agent=create_denial_management_agent()
    )
    await denial_task.execute()

elif claim_status_result.get("outcome") == "complete":
    payment_task = Task(
        description=f"Post payment for claim {claim_id}. Paid amount: {claim_status_result.get('payment_amount')}",
        expected_output="Confirmation of payment posting and final patient responsibility.",
        agent=create_payment_posting_agent()
    )
    await payment_task.execute()

```

