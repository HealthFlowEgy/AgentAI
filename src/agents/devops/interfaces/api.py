"""FastAPI router for the DevOps agent.

Endpoints:
    POST /api/devops/chat          SSE stream of agent output
    POST /api/devops/approve       Resolve a pending approval (admin only)
    GET  /api/devops/approvals     List in-flight approvals (admin only)
    GET  /api/devops/health        Liveness probe
    POST /api/devops/slack/events       (defined in slack.py, mounted here)
    POST /api/devops/slack/interactive  (defined in slack.py, mounted here)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from config.settings import settings
from src.agents.devops.audit import redact
from src.agents.devops.permissions import FutureBackedBroker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devops", tags=["devops"])


# Process-wide singleton broker. The Slack handler shares it so a Slack
# Approve click can resolve a request originating from an HTTP chat
# session and vice versa.
broker = FutureBackedBroker(
    interface="api",
    timeout_s=settings.DEVOPS_APPROVAL_TIMEOUT_S,
)


# --- Models -----------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    read_only: bool | None = None


class ApprovalDecision(BaseModel):
    approval_id: str
    decision: str = Field(pattern="^(allow|deny)$")
    updated_input: dict | None = None
    reason: str | None = None


# --- Auth helper (lazy) -----------------------------------------------------


def _auth_dep():
    """Return the project's JWT dependency, or a stub for tests."""
    try:
        from src.core.auth import get_current_user

        return get_current_user
    except Exception:  # noqa: BLE001
        # Tests without the full app stack get an open endpoint.
        async def _open():
            return type("AnonUser", (), {"id": "test", "role": "admin", "active": True})()

        return _open


_get_user = _auth_dep()


def _require_admin(user) -> None:
    role = getattr(user, "role", None)
    role_str = role.value if hasattr(role, "value") else role
    if role_str != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DevOps approvals are restricted to admin users.",
        )


# --- Endpoints --------------------------------------------------------------


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/approvals")
async def list_approvals(user=Depends(_get_user)) -> list[dict]:
    _require_admin(user)
    return [
        {
            "approval_id": req.approval_id,
            "tool": req.tool_name,
            "input": redact(req.input_data),
            "requested_at": req.requested_at,
        }
        for req in broker.pending.values()
    ]


@router.post("/approve")
async def approve(decision: ApprovalDecision, user=Depends(_get_user)) -> dict:
    _require_admin(user)
    decided_by = getattr(user, "id", "admin")
    ok = broker.resolve(
        decision.approval_id,
        allowed=(decision.decision == "allow"),
        updated_input=decision.updated_input,
        reason=decision.reason,
        decided_by=str(decided_by),
    )
    if not ok:
        raise HTTPException(404, "approval_id not found or already resolved")
    return {"resolved": True}


@router.post("/chat")
async def chat(req: ChatRequest, user=Depends(_get_user)) -> EventSourceResponse:
    """SSE stream of agent messages.

    Frames:
      event: token         data: {"text": "..."}
      event: tool_use      data: {"name": "...", "input": {...redacted...}}
      event: approval_required  data: {"approval_id": "...", "tool": "...", "input": {...}}
      event: tool_result   data: {"name": "...", "ok": true}
      event: done          data: {}
    """
    from src.agents.devops.agent import open_session

    async def event_gen():
        async with open_session(broker=broker, read_only_mode=req.read_only) as client:
            await client.query(req.message, session_id=req.session_id)
            async for msg in client.receive_response():
                event_name, payload = _classify(msg)
                if event_name is None:
                    continue
                yield {"event": event_name, "data": json.dumps(payload)}
            yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_gen())


def _classify(msg: Any) -> tuple[str | None, dict]:
    """Best-effort mapping of SDK message objects to SSE frames.

    The SDK exposes several message types; we key off attribute presence so
    we don't have to import the SDK's type names at import time.
    """
    if hasattr(msg, "text") and msg.text:
        return "token", {"text": msg.text}
    if hasattr(msg, "tool_name") and hasattr(msg, "tool_input"):
        return (
            "tool_use",
            {"name": msg.tool_name, "input": redact(getattr(msg, "tool_input", {}))},
        )
    if hasattr(msg, "tool_result"):
        return (
            "tool_result",
            {"name": getattr(msg, "tool_name", "?"), "ok": getattr(msg, "is_error", False) is False},
        )
    return None, {}


# Mount Slack endpoints on the same router so /api/devops/slack/* is the URL.
try:
    from src.agents.devops.interfaces.slack import slack_router

    router.include_router(slack_router)
except Exception as exc:  # noqa: BLE001
    logger.info("Slack DevOps endpoints not mounted: %s", exc)
