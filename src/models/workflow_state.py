"""
Workflow State Management Models
Enables workflows to persist state, resume from failures, and track progress
"""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, ENUM
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum as PyEnum
from pydantic import BaseModel, Field
from src.services.database import Base


class WorkflowStatus(str, PyEnum):
    """Workflow execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class WorkflowStepStatus(str, PyEnum):
    """Individual step status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


# ===== SQLAlchemy Models (Database) =====

class WorkflowStateModel(Base):
    """
    Database model for workflow state persistence
    Allows resuming workflows from any point of failure
    """
    __tablename__ = "workflow_state"
    
    # Primary identification
    workflow_id = Column(String(50), primary_key=True)
    encounter_id = Column(String(50), ForeignKey('encounters.encounter_id'), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False, default="end_to_end_rcm")
    
    # Progress tracking
    current_step = Column(Integer, nullable=False, default=0)
    total_steps = Column(Integer, nullable=False)
    completed_steps = Column(ARRAY(String), default=list)
    
    # Status
    status = Column(
        ENUM(WorkflowStatus, name='workflow_status_enum'),
        nullable=False,
        default=WorkflowStatus.PENDING,
        index=True
    )
    
    # Results storage (JSONB for efficient querying)
    step_results = Column(JSON, default=dict)
    workflow_metadata = Column(JSON, default=dict)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_step = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Performance metrics
    total_execution_time_ms = Column(Integer, nullable=True)
    
    # Relationships
    steps = relationship("WorkflowStepModel", back_populates="workflow", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkflowState(id={self.workflow_id}, status={self.status}, step={self.current_step}/{self.total_steps})>"


class WorkflowStepModel(Base):
    """
    Individual workflow step tracking
    Stores detailed execution information for each step
    """
    __tablename__ = "workflow_steps"
    
    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String(50), ForeignKey('workflow_state.workflow_id'), nullable=False)
    step_name = Column(String(100), nullable=False)
    step_number = Column(Integer, nullable=False)
    
    # Agent information
    agent_name = Column(String(100), nullable=False)
    agent_version = Column(String(20), default="1.0.0")
    
    # Status
    status = Column(
        ENUM(WorkflowStepStatus, name='workflow_step_status_enum'),
        nullable=False,
        default=WorkflowStepStatus.PENDING
    )
    
    # Data
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    error_details = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    # Retry tracking
    attempt_number = Column(Integer, default=1)
    max_retries = Column(Integer, default=3)
    
    # Relationships
    workflow = relationship("WorkflowStateModel", back_populates="steps")
    
    def __repr__(self):
        return f"<WorkflowStep(workflow={self.workflow_id}, step={self.step_name}, status={self.status})>"


# ===== Pydantic Models (API/Logic) =====

class WorkflowStepResult(BaseModel):
    """Result of a single workflow step"""
    step_name: str
    agent_name: str
    status: WorkflowStepStatus
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    execution_time_ms: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    attempt_number: int = 1
    
    class Config:
        use_enum_values = True


class WorkflowState(BaseModel):
    """Workflow state for business logic"""
    workflow_id: str
    encounter_id: str
    workflow_type: str = "end_to_end_rcm"
    current_step: int = 0
    total_steps: int
    completed_steps: List[str] = Field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    step_results: Dict[str, WorkflowStepResult] = Field(default_factory=dict)
    workflow_metadata: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    retry_count: int = 0
    total_execution_time_ms: Optional[int] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def is_complete(self) -> bool:
        """Check if workflow is complete"""
        return self.status == WorkflowStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if workflow has failed"""
        return self.status == WorkflowStatus.FAILED
    
    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if workflow can be retried"""
        return self.is_failed() and self.retry_count < max_retries
    
    def get_next_step(self) -> Optional[int]:
        """Get next step number to execute"""
        if self.current_step < self.total_steps:
            return self.current_step + 1
        return None
    
    def progress_percentage(self) -> float:
        """Calculate workflow progress percentage"""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100


class WorkflowResume(BaseModel):
    """Request to resume a workflow"""
    workflow_id: str
    from_step: Optional[int] = None  # If None, resume from last completed step
    skip_failed_step: bool = False
    retry_config: Optional[Dict[str, Any]] = None


class WorkflowResult(BaseModel):
    """Final workflow result"""
    workflow_id: str
    encounter_id: str
    status: WorkflowStatus
    completed_steps: List[str]
    step_results: Dict[str, WorkflowStepResult]
    total_execution_time_ms: int
    started_at: datetime
    completed_at: datetime
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowMetrics(BaseModel):
    """Workflow performance metrics"""
    total_workflows: int
    completed: int
    failed: int
    in_progress: int
    average_execution_time_ms: float
    success_rate: float
    step_performance: Dict[str, Dict[str, float]]  # step_name -> {avg_time, success_rate}
    
    @classmethod
    def calculate(cls, workflows: List[WorkflowState]) -> "WorkflowMetrics":
        """Calculate metrics from workflow list"""
        total = len(workflows)
        completed = sum(1 for w in workflows if w.is_complete())
        failed = sum(1 for w in workflows if w.is_failed())
        in_progress = sum(1 for w in workflows if w.status == WorkflowStatus.IN_PROGRESS)
        
        # Average execution time (only completed workflows)
        completed_workflows = [w for w in workflows if w.is_complete()]
        avg_time = (
            sum(w.total_execution_time_ms or 0 for w in completed_workflows) / len(completed_workflows)
            if completed_workflows else 0.0
        )
        
        success_rate = (completed / total * 100) if total > 0 else 0.0
        
        # Step performance analysis
        step_performance = {}
        for workflow in completed_workflows:
            for step_name, result in workflow.step_results.items():
                if step_name not in step_performance:
                    step_performance[step_name] = {
                        "total_time": 0,
                        "count": 0,
                        "successes": 0
                    }
                
                step_performance[step_name]["total_time"] += result.execution_time_ms
                step_performance[step_name]["count"] += 1
                if result.status == WorkflowStepStatus.COMPLETED:
                    step_performance[step_name]["successes"] += 1
        
        # Calculate averages
        for step_name, data in step_performance.items():
            count = data["count"]
            step_performance[step_name] = {
                "avg_time_ms": data["total_time"] / count if count > 0 else 0,
                "success_rate": (data["successes"] / count * 100) if count > 0 else 0
            }
        
        return cls(
            total_workflows=total,
            completed=completed,
            failed=failed,
            in_progress=in_progress,
            average_execution_time_ms=avg_time,
            success_rate=success_rate,
            step_performance=step_performance
        )