"""
Stateful RCM Workflow with Resume Capability
Implements workflow state management for fault tolerance
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from src.models.workflow_state import (
    WorkflowState,
    WorkflowStateModel,
    WorkflowStepModel,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepResult,
    WorkflowResult
)
from src.models.rcm_models import EncounterData
from praisonaiagents import Task, Agent

logger = logging.getLogger(__name__)


class WorkflowTimeoutError(Exception):
    """Raised when workflow exceeds timeout"""
    pass


class WorkflowStep:
    """
    Represents a single workflow step with retry capability
    """
    def __init__(
        self,
        name: str,
        agent: Agent,
        description: str,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        depends_on: Optional[List[str]] = None
    ):
        self.name = name
        self.agent = agent
        self.description = description
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.depends_on = depends_on or []
    
    async def execute(
        self,
        encounter_data: EncounterData,
        previous_results: Dict[str, WorkflowStepResult],
        attempt: int = 1
    ) -> WorkflowStepResult:
        """Execute the workflow step with timeout"""
        start_time = datetime.utcnow()
        
        try:
            # Create task for agent
            task = Task(
                description=self.description,
                expected_output=f"Completed {self.name}",
                agent=self.agent,
                context=list(previous_results.values()) if previous_results else None
            )
            
            # Execute with timeout
            result = await asyncio.wait_for(
                task.execute_async(),
                timeout=self.timeout_seconds
            )
            
            end_time = datetime.utcnow()
            execution_time = int((end_time - start_time).total_seconds() * 1000)
            
            return WorkflowStepResult(
                step_name=self.name,
                agent_name=self.agent.name,
                status=WorkflowStepStatus.COMPLETED,
                input_data={"encounter_id": encounter_data.encounter_id},
                output_data=result,
                execution_time_ms=execution_time,
                started_at=start_time,
                completed_at=end_time,
                attempt_number=attempt
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Step {self.name} timed out after {self.timeout_seconds}s")
            end_time = datetime.utcnow()
            execution_time = int((end_time - start_time).total_seconds() * 1000)
            
            return WorkflowStepResult(
                step_name=self.name,
                agent_name=self.agent.name,
                status=WorkflowStepStatus.FAILED,
                input_data={"encounter_id": encounter_data.encounter_id},
                output_data={},
                error_message=f"Timeout after {self.timeout_seconds} seconds",
                error_details={"type": "TimeoutError"},
                execution_time_ms=execution_time,
                started_at=start_time,
                attempt_number=attempt
            )
            
        except Exception as e:
            logger.error(f"Step {self.name} failed: {e}", exc_info=True)
            end_time = datetime.utcnow()
            execution_time = int((end_time - start_time).total_seconds() * 1000)
            
            return WorkflowStepResult(
                step_name=self.name,
                agent_name=self.agent.name,
                status=WorkflowStepStatus.FAILED,
                input_data={"encounter_id": encounter_data.encounter_id},
                output_data={},
                error_message=str(e),
                error_details={"type": type(e).__name__, "message": str(e)},
                execution_time_ms=execution_time,
                started_at=start_time,
                attempt_number=attempt
            )


class StatefulRCMWorkflow:
    """
    Stateful workflow with persistence and resume capability
    """
    
    def __init__(self, db: Session, agents: Dict[str, Agent]):
        self.db = db
        self.agents = agents
        self.steps = self._define_steps()
    
    def _define_steps(self) -> List[WorkflowStep]:
        """Define all workflow steps"""
        return [
            WorkflowStep(
                name="registration",
                agent=self.agents["registration"],
                description="Register patient and verify demographics",
                timeout_seconds=60
            ),
            WorkflowStep(
                name="eligibility",
                agent=self.agents["eligibility"],
                description="Verify insurance eligibility via HCX",
                timeout_seconds=120,
                depends_on=["registration"]
            ),
            WorkflowStep(
                name="pre_authorization",
                agent=self.agents["pre_auth"],
                description="Obtain pre-authorization if required",
                timeout_seconds=180,
                depends_on=["eligibility"]
            ),
            WorkflowStep(
                name="medical_coding",
                agent=self.agents["medical_coder"],
                description="Assign ICD-10 and CPT codes",
                timeout_seconds=120,
                depends_on=["registration"]
            ),
            WorkflowStep(
                name="charge_audit",
                agent=self.agents["charge_auditor"],
                description="Audit charges for completeness",
                timeout_seconds=90,
                depends_on=["medical_coding"]
            ),
            WorkflowStep(
                name="fhir_generation",
                agent=self.agents["fhir_generator"],
                description="Generate FHIR R4 Claim resource",
                timeout_seconds=60,
                depends_on=["medical_coding", "charge_audit"]
            ),
            WorkflowStep(
                name="scrubbing",
                agent=self.agents["scrubber"],
                description="Validate and scrub claim",
                timeout_seconds=90,
                depends_on=["fhir_generation"]
            ),
            WorkflowStep(
                name="submission",
                agent=self.agents["submission"],
                description="Submit claim to HCX platform",
                timeout_seconds=120,
                depends_on=["scrubbing", "pre_authorization"]
            ),
            WorkflowStep(
                name="status_tracking",
                agent=self.agents["status_tracker"],
                description="Track claim status",
                timeout_seconds=60,
                depends_on=["submission"]
            )
        ]
    
    async def create_workflow(self, encounter_data: EncounterData) -> WorkflowState:
        """Create new workflow state"""
        workflow_id = f"WF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        state = WorkflowStateModel(
            workflow_id=workflow_id,
            encounter_id=encounter_data.encounter_id,
            workflow_type="end_to_end_rcm",
            current_step=0,
            total_steps=len(self.steps),
            status=WorkflowStatus.PENDING
        )
        
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        
        logger.info(f"Created workflow {workflow_id} for encounter {encounter_data.encounter_id}")
        
        return self._model_to_pydantic(state)
    
    async def load_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """Load existing workflow state"""
        db_state = self.db.query(WorkflowStateModel).filter_by(
            workflow_id=workflow_id
        ).first()
        
        if not db_state:
            return None
        
        return self._model_to_pydantic(db_state)
    
    async def save_workflow(self, state: WorkflowState):
        """Persist workflow state"""
        db_state = self.db.query(WorkflowStateModel).filter_by(
            workflow_id=state.workflow_id
        ).first()
        
        if not db_state:
            raise ValueError(f"Workflow {state.workflow_id} not found")
        
        # Update state
        db_state.current_step = state.current_step
        db_state.completed_steps = state.completed_steps
        db_state.status = state.status.value
        db_state.step_results = {
            name: result.dict() for name, result in state.step_results.items()
        }
        db_state.workflow_metadata = state.workflow_metadata
        db_state.updated_at = datetime.utcnow()
        db_state.completed_at = state.completed_at
        db_state.error_message = state.error_message
        db_state.error_step = state.error_step
        db_state.retry_count = state.retry_count
        db_state.total_execution_time_ms = state.total_execution_time_ms
        
        self.db.commit()
    
    async def save_step_result(
        self,
        workflow_id: str,
        step_result: WorkflowStepResult
    ):
        """Save individual step result"""
        step_model = WorkflowStepModel(
            workflow_id=workflow_id,
            step_name=step_result.step_name,
            step_number=len(self.db.query(WorkflowStepModel).filter_by(
                workflow_id=workflow_id
            ).all()) + 1,
            agent_name=step_result.agent_name,
            status=step_result.status.value,
            input_data=step_result.input_data,
            output_data=step_result.output_data,
            error_details=step_result.error_details,
            started_at=step_result.started_at,
            completed_at=step_result.completed_at,
            execution_time_ms=step_result.execution_time_ms,
            attempt_number=step_result.attempt_number
        )
        
        self.db.add(step_model)
        self.db.commit()
    
    async def process_encounter(
        self,
        encounter_data: EncounterData,
        resume: bool = False,
        workflow_id: Optional[str] = None
    ) -> WorkflowResult:
        """
        Process encounter through complete RCM workflow with state management
        """
        workflow_start = datetime.utcnow()
        
        # Load or create workflow
        if resume and workflow_id:
            state = await self.load_workflow(workflow_id)
            if not state:
                raise ValueError(f"Workflow {workflow_id} not found")
            logger.info(f"Resuming workflow {workflow_id} from step {state.current_step}")
        else:
            state = await self.create_workflow(encounter_data)
        
        # Update status to in progress
        state.status = WorkflowStatus.IN_PROGRESS
        await self.save_workflow(state)
        
        try:
            # Execute remaining steps
            for i, step in enumerate(self.steps[state.current_step:], start=state.current_step):
                logger.info(f"Executing step {i+1}/{len(self.steps)}: {step.name}")
                
                # Check dependencies
                if not self._check_dependencies(step, state.step_results):
                    logger.warning(f"Skipping step {step.name} - dependencies not met")
                    continue
                
                # Execute step with retry logic
                attempt = 1
                result = None
                
                while attempt <= step.max_retries:
                    result = await step.execute(
                        encounter_data,
                        state.step_results,
                        attempt
                    )
                    
                    if result.status == WorkflowStepStatus.COMPLETED:
                        break
                    
                    if attempt < step.max_retries:
                        logger.warning(
                            f"Step {step.name} failed (attempt {attempt}/{step.max_retries}), retrying..."
                        )
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                    attempt += 1
                
                # Save step result
                state.step_results[step.name] = result
                await self.save_step_result(state.workflow_id, result)
                
                # Check if step failed after all retries
                if result.status == WorkflowStepStatus.FAILED:
                    logger.error(f"Step {step.name} failed after {step.max_retries} attempts")
                    state.status = WorkflowStatus.FAILED
                    state.error_message = result.error_message
                    state.error_step = step.name
                    await self.save_workflow(state)
                    raise Exception(f"Step {step.name} failed: {result.error_message}")
                
                # Update progress
                state.current_step = i + 1
                state.completed_steps.append(step.name)
                state.updated_at = datetime.utcnow()
                await self.save_workflow(state)
            
            # Mark workflow as completed
            workflow_end = datetime.utcnow()
            state.status = WorkflowStatus.COMPLETED
            state.completed_at = workflow_end
            state.total_execution_time_ms = int(
                (workflow_end - workflow_start).total_seconds() * 1000
            )
            await self.save_workflow(state)
            
            logger.info(
                f"Workflow {state.workflow_id} completed in "
                f"{state.total_execution_time_ms}ms"
            )
            
            return WorkflowResult(
                workflow_id=state.workflow_id,
                encounter_id=state.encounter_id,
                status=state.status,
                completed_steps=state.completed_steps,
                step_results=state.step_results,
                total_execution_time_ms=state.total_execution_time_ms,
                started_at=state.started_at,
                completed_at=state.completed_at
            )
            
        except Exception as e:
            logger.error(f"Workflow {state.workflow_id} failed: {e}", exc_info=True)
            
            # Update state to failed
            state.status = WorkflowStatus.FAILED
            state.error_message = str(e)
            state.updated_at = datetime.utcnow()
            await self.save_workflow(state)
            
            raise
    
    def _check_dependencies(
        self,
        step: WorkflowStep,
        completed_results: Dict[str, WorkflowStepResult]
    ) -> bool:
        """Check if step dependencies are met"""
        for dep in step.depends_on:
            if dep not in completed_results:
                return False
            if completed_results[dep].status != WorkflowStepStatus.COMPLETED:
                return False
        return True
    
    def _model_to_pydantic(self, db_state: WorkflowStateModel) -> WorkflowState:
        """Convert SQLAlchemy model to Pydantic model"""
        step_results = {}
        if db_state.step_results:
            for name, result_dict in db_state.step_results.items():
                step_results[name] = WorkflowStepResult(**result_dict)
        
        return WorkflowState(
            workflow_id=db_state.workflow_id,
            encounter_id=db_state.encounter_id,
            workflow_type=db_state.workflow_type,
            current_step=db_state.current_step,
            total_steps=db_state.total_steps,
            completed_steps=db_state.completed_steps or [],
            status=WorkflowStatus(db_state.status),
            step_results=step_results,
            workflow_metadata=db_state.workflow_metadata or {},
            started_at=db_state.started_at,
            updated_at=db_state.updated_at,
            completed_at=db_state.completed_at,
            error_message=db_state.error_message,
            error_step=db_state.error_step,
            retry_count=db_state.retry_count,
            total_execution_time_ms=db_state.total_execution_time_ms
        )
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get current workflow status"""
        return await self.load_workflow(workflow_id)
    
    async def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
        encounter_id: Optional[str] = None,
        limit: int = 100
    ) -> List[WorkflowState]:
        """List workflows with filters"""
        query = self.db.query(WorkflowStateModel)
        
        if status:
            query = query.filter(WorkflowStateModel.status == status.value)
        
        if encounter_id:
            query = query.filter(WorkflowStateModel.encounter_id == encounter_id)
        
        query = query.order_by(WorkflowStateModel.started_at.desc()).limit(limit)
        
        db_states = query.all()
        return [self._model_to_pydantic(state) for state in db_states]