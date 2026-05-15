"""Slack endpoints for the DevOps agent.

Mounts under the same FastAPI router as the API:
    POST /api/devops/slack/events
    POST /api/devops/slack/interactive
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from config.settings import settings
from src.agents.devops.audit import redact

logger = logging.getLogger(__name__)

slack_router = APIRouter(prefix="/slack", tags=["devops-slack"])


def _verifier():
    if not settings.SLACK_SIGNING_SECRET:
        return None
    from slack_sdk.signature import SignatureVerifier  # type: ignore

    return SignatureVerifier(settings.SLACK_SIGNING_SECRET)


async def _verify(request: Request, body: bytes, timestamp: str | None, signature: str | None) -> None:
    verifier = _verifier()
    if verifier is None:
        return  # signing not configured: accept (dev only)
    if not timestamp or not signature:
        raise HTTPException(401, "missing Slack signature headers")
    if not verifier.is_valid(body=body.decode("utf-8"), timestamp=timestamp, signature=signature):
        raise HTTPException(401, "bad Slack signature")


@slack_router.post("/events")
async def slack_events(
    request: Request,
    x_slack_request_timestamp: str | None = Header(default=None),
    x_slack_signature: str | None = Header(default=None),
) -> dict:
    body = await request.body()
    await _verify(request, body, x_slack_request_timestamp, x_slack_signature)

    payload = json.loads(body)
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    # Other event types accepted but not yet handled in v1.
    return {"ok": True}


@slack_router.post("/interactive")
async def slack_interactive(
    request: Request,
    x_slack_request_timestamp: str | None = Header(default=None),
    x_slack_signature: str | None = Header(default=None),
) -> dict:
    body = await request.body()
    await _verify(request, body, x_slack_request_timestamp, x_slack_signature)

    # Slack posts as application/x-www-form-urlencoded with a `payload` field.
    from urllib.parse import parse_qs

    form = parse_qs(body.decode("utf-8"))
    raw = form.get("payload", [None])[0]
    if not raw:
        raise HTTPException(400, "missing payload")
    payload = json.loads(raw)

    user_id = payload.get("user", {}).get("id")
    if user_id not in (settings.DEVOPS_SLACK_APPROVERS or []):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not in approvers list")

    actions = payload.get("actions") or []
    if not actions:
        raise HTTPException(400, "no action in payload")
    action = actions[0]
    block_id = action.get("block_id", "")
    value = action.get("value", "")

    if ":" in value:
        approval_id, decision = value.split(":", 1)
    else:
        approval_id, decision = block_id, value

    from src.agents.devops.interfaces.api import broker

    ok = broker.resolve(
        approval_id,
        allowed=(decision == "allow"),
        decided_by=f"slack:{user_id}",
        reason=None if decision == "allow" else "Denied via Slack",
    )
    return {"ok": ok}


def build_approval_blocks(approval_id: str, tool_name: str, input_data: dict) -> list[dict]:
    """Block Kit payload for an approval card."""
    return [
        {
            "type": "section",
            "block_id": approval_id,
            "text": {
                "type": "mrkdwn",
                "text": f"*Approval required:* `{tool_name}`\n```{json.dumps(redact(input_data), indent=2)}```",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "value": f"{approval_id}:allow",
                    "action_id": "approve",
                },
                {
                    "type": "button",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "value": f"{approval_id}:deny",
                    "action_id": "deny",
                },
            ],
        },
    ]
