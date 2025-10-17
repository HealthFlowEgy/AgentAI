"""
Prometheus Metrics for RCM System Monitoring
Tracks performance, errors, and business metrics
"""
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    generate_latest,
    REGISTRY
)
from functools import wraps
from typing import Callable
import time
import logging

logger = logging.getLogger(__name__)

# ===== Application Info =====
app_info = Info('rcm_application', 'RCM System Information')
app_info.info({
    'version': '1.0.0',
    'environment': 'production'
})

# ===== Workflow Metrics =====
workflows_total = Counter(
    'rcm_workflows_total',
    'Total number of workflows started',
    ['workflow_type']
)

workflows_completed = Counter(
    'rcm_workflows_completed_total',
    'Total number of workflows completed successfully',
    ['workflow_type']
)

workflows_failed = Counter(
    'rcm_workflows_failed_total',
    'Total number of workflows failed',
    ['workflow_type', 'error_type']
)

workflow_duration = Histogram(
    'rcm_workflow_duration_seconds',
    'Workflow execution time in seconds',
    ['workflow_type'],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600)
)

active_workflows = Gauge(
    'rcm_active_workflows',
    'Number of workflows currently in progress',
    ['workflow_type']
)

workflow_step_duration = Histogram(
    'rcm_workflow_step_duration_seconds',
    'Individual step execution time',
    ['workflow_type', 'step_name', 'agent_name'],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120)
)

workflow_step_retries = Counter(
    'rcm_workflow_step_retries_total',
    'Number of step retries',
    ['workflow_type', 'step_name', 'agent_name']
)

# ===== Claims Metrics =====
claims_submitted = Counter(
    'rcm_claims_submitted_total',
    'Total claims submitted to HCX',
    ['payer', 'claim_type']
)

claims_approved = Counter(
    'rcm_claims_approved_total',
    'Total claims approved by payers',
    ['payer']
)

claims_denied = Counter(
    'rcm_claims_denied_total',
    'Total claims denied',
    ['payer', 'denial_reason']
)

claim_amount = Histogram(
    'rcm_claim_amount_egp',
    'Claim amounts in EGP',
    ['payer', 'claim_type'],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000)
)

claim_processing_time = Histogram(
    'rcm_claim_processing_seconds',
    'Time from submission to adjudication',
    ['payer'],
    buckets=(3600, 86400, 172800, 604800, 1209600)  # 1h, 1d, 2d, 7d, 14d
)

# ===== HCX API Metrics =====
hcx_api_requests = Counter(
    'rcm_hcx_api_requests_total',
    'Total HCX API requests',
    ['endpoint', 'method']
)

hcx_api_responses = Counter(
    'rcm_hcx_api_responses_total',
    'HCX API responses by status',
    ['endpoint', 'status_code']
)

hcx_api_duration = Histogram(
    'rcm_hcx_api_duration_seconds',
    'HCX API request duration',
    ['endpoint'],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30)
)

hcx_api_errors = Counter(
    'rcm_hcx_api_errors_total',
    'HCX API errors',
    ['endpoint', 'error_type']
)

hcx_token_refreshes = Counter(
    'rcm_hcx_token_refreshes_total',
    'Number of HCX token refreshes'
)

# ===== Agent Performance =====
agent_executions = Counter(
    'rcm_agent_executions_total',
    'Total agent executions',
    ['agent_name', 'task_type']
)

agent_execution_time = Histogram(
    'rcm_agent_execution_seconds',
    'Agent execution time',
    ['agent_name', 'task_type'],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300)
)

agent_errors = Counter(
    'rcm_agent_errors_total',
    'Agent execution errors',
    ['agent_name', 'error_type']
)

agent_llm_calls = Counter(
    'rcm_agent_llm_calls_total',
    'LLM API calls by agent',
    ['agent_name', 'model']
)

agent_llm_tokens = Counter(
    'rcm_agent_llm_tokens_total',
    'LLM tokens used',
    ['agent_name', 'model', 'type']  # type: prompt or completion
)

# ===== Database Metrics =====
db_connections = Gauge(
    'rcm_db_connections',
    'Active database connections'
)

db_query_duration = Histogram(
    'rcm_db_query_duration_seconds',
    'Database query execution time',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5)
)

db_errors = Counter(
    'rcm_db_errors_total',
    'Database errors',
    ['operation', 'error_type']
)

# ===== Business Metrics =====
revenue_captured = Counter(
    'rcm_revenue_captured_egp',
    'Total revenue captured',
    ['payer', 'service_type']
)

denial_rate = Gauge(
    'rcm_denial_rate_percent',
    'Current denial rate percentage',
    ['payer']
)

clean_claim_rate = Gauge(
    'rcm_clean_claim_rate_percent',
    'Percentage of claims submitted without errors',
    ['payer']
)

days_in_ar = Gauge(
    'rcm_days_in_ar',
    'Average days in accounts receivable',
    ['payer']
)

# ===== System Metrics =====
system_errors = Counter(
    'rcm_system_errors_total',
    'System-level errors',
    ['component', 'error_type']
)

http_requests = Counter(
    'rcm_http_requests_total',
    'HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration = Histogram(
    'rcm_http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10)
)


# ===== Decorators for Easy Instrumentation =====

def track_workflow(workflow_type: str = "end_to_end_rcm"):
    """Decorator to track workflow metrics"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            workflows_total.labels(workflow_type=workflow_type).inc()
            active_workflows.labels(workflow_type=workflow_type).inc()
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                workflows_completed.labels(workflow_type=workflow_type).inc()
                return result
            except Exception as e:
                error_type = type(e).__name__
                workflows_failed.labels(
                    workflow_type=workflow_type,
                    error_type=error_type
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                workflow_duration.labels(workflow_type=workflow_type).observe(duration)
                active_workflows.labels(workflow_type=workflow_type).dec()
        
        return wrapper
    return decorator


def track_agent(agent_name: str, task_type: str = "general"):
    """Decorator to track agent execution metrics"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            agent_executions.labels(
                agent_name=agent_name,
                task_type=task_type
            ).inc()
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                agent_errors.labels(
                    agent_name=agent_name,
                    error_type=error_type
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                agent_execution_time.labels(
                    agent_name=agent_name,
                    task_type=task_type
                ).observe(duration)
        
        return wrapper
    return decorator


def track_hcx_call(endpoint: str):
    """Decorator to track HCX API calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            hcx_api_requests.labels(
                endpoint=endpoint,
                method="POST"
            ).inc()
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                
                # Track response status
                if isinstance(result, dict):
                    status = result.get("status", "unknown")
                    if status == "success":
                        hcx_api_responses.labels(
                            endpoint=endpoint,
                            status_code="200"
                        ).inc()
                    elif status == "error":
                        error_type = result.get("error_type", "unknown")
                        hcx_api_errors.labels(
                            endpoint=endpoint,
                            error_type=error_type
                        ).inc()
                
                return result
            finally:
                duration = time.time() - start_time
                hcx_api_duration.labels(endpoint=endpoint).observe(duration)
        
        return wrapper
    return decorator


def track_db_query(operation: str):
    """Decorator to track database queries"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                db_errors.labels(
                    operation=operation,
                    error_type=error_type
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                db_query_duration.labels(operation=operation).observe(duration)
        
        return wrapper
    return decorator


# ===== Metric Collection Functions =====

def record_claim_submission(payer: str, claim_type: str, amount: float):
    """Record claim submission"""
    claims_submitted.labels(payer=payer, claim_type=claim_type).inc()
    claim_amount.labels(payer=payer, claim_type=claim_type).observe(amount)
    revenue_captured.labels(payer=payer, service_type=claim_type).inc(amount)


def record_claim_approval(payer: str, amount: float):
    """Record claim approval"""
    claims_approved.labels(payer=payer).inc()


def record_claim_denial(payer: str, denial_reason: str):
    """Record claim denial"""
    claims_denied.labels(payer=payer, denial_reason=denial_reason).inc()


def record_llm_usage(agent_name: str, model: str, prompt_tokens: int, completion_tokens: int):
    """Record LLM token usage"""
    agent_llm_calls.labels(agent_name=agent_name, model=model).inc()
    agent_llm_tokens.labels(agent_name=agent_name, model=model, type="prompt").inc(prompt_tokens)
    agent_llm_tokens.labels(agent_name=agent_name, model=model, type="completion").inc(completion_tokens)


def update_business_metrics(
    payer: str,
    denial_rate_pct: float,
    clean_claim_rate_pct: float,
    days_ar: float
):
    """Update business KPI metrics"""
    denial_rate.labels(payer=payer).set(denial_rate_pct)
    clean_claim_rate.labels(payer=payer).set(clean_claim_rate_pct)
    days_in_ar.labels(payer=payer).set(days_ar)


def get_metrics() -> bytes:
    """Get all metrics in Prometheus format"""
    return generate_latest(REGISTRY)


# ===== Middleware for HTTP Metrics =====

class MetricsMiddleware:
    """Middleware to track HTTP request metrics"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope["method"]
        path = scope["path"]
        
        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time
                
                # Record metrics
                http_requests.labels(
                    method=method,
                    endpoint=path,
                    status_code=str(status_code)
                ).inc()
                
                http_request_duration.labels(
                    method=method,
                    endpoint=path
                ).observe(duration)
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)