"""Structured audit log for every DevOps tool call and approval decision."""
from __future__ import annotations

import time
from typing import Any

import structlog

_logger = structlog.get_logger("devops.audit")

_SECRET_KEYS = {
    "token", "secret", "password", "key", "authorization",
    "github_token", "digitalocean_token", "anthropic_api_key",
}


def redact(value: Any) -> Any:
    """Recursively redact obvious secret-bearing fields in tool input."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(s in k.lower() for s in _SECRET_KEYS):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def log_decision(
    *,
    tool_name: str,
    input_data: dict,
    decision: str,
    decided_by: str,
    interface: str,
    requested_at: float,
    reason: str | None = None,
) -> None:
    """Write one structured line per approval decision."""
    _logger.info(
        "devops.tool.decision",
        tool=tool_name,
        input=redact(input_data),
        decision=decision,
        decided_by=decided_by,
        interface=interface,
        latency_ms=int((time.time() - requested_at) * 1000),
        reason=reason,
    )


def log_tool_result(
    *,
    tool_name: str,
    ok: bool,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Write one line per tool execution result."""
    _logger.info(
        "devops.tool.result",
        tool=tool_name,
        ok=ok,
        duration_ms=duration_ms,
        error=error,
    )
