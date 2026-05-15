"""Permission gating for DevOps tools.

The single source of truth for "is this tool safe to auto-approve?" is the
``readOnlyHint`` annotation on each ``@tool``. ``can_use_tool`` consults it
and either auto-allows, denies (read-only mode), or delegates to a pluggable
``ApprovalBroker`` that can prompt a human via CLI / FastAPI / Slack.
"""
from __future__ import annotations

import abc
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from src.agents.devops import audit


@dataclass
class ApprovalRequest:
    approval_id: str
    tool_name: str
    input_data: dict
    requested_at: float
    requested_by: str = "agent"
    interface: str = "unknown"
    future: asyncio.Future = field(default_factory=asyncio.Future)


@dataclass
class ApprovalResult:
    allowed: bool
    updated_input: dict | None = None
    reason: str | None = None
    decided_by: str = "unknown"


class ApprovalBroker(abc.ABC):
    """Pluggable approval backend. CLI / FastAPI / Slack each register one."""

    interface: str = "abstract"

    @abc.abstractmethod
    async def request(self, req: ApprovalRequest) -> ApprovalResult:
        """Block until a human (or timeout) decides on the request."""


class AutoAllowBroker(ApprovalBroker):
    """Test/dev convenience: approve every mutation. Never use in prod."""

    interface = "auto-allow"

    async def request(self, req: ApprovalRequest) -> ApprovalResult:
        return ApprovalResult(allowed=True, decided_by="auto-allow")


class AutoDenyBroker(ApprovalBroker):
    """Useful default when no human approver is wired up."""

    interface = "auto-deny"

    async def request(self, req: ApprovalRequest) -> ApprovalResult:
        return ApprovalResult(
            allowed=False,
            reason="No approval interface configured for this session.",
            decided_by="auto-deny",
        )


class FutureBackedBroker(ApprovalBroker):
    """Backend that suspends on an asyncio.Future resolved out-of-band.

    Used by both the FastAPI router (resolved by POST /approve) and the
    Slack interactive endpoint (resolved by button clicks). The interface
    label distinguishes which surface decided.
    """

    def __init__(self, *, interface: str, timeout_s: int):
        self.interface = interface
        self.timeout_s = timeout_s
        self.pending: dict[str, ApprovalRequest] = {}

    def new_request(
        self,
        *,
        tool_name: str,
        input_data: dict,
        requested_by: str = "agent",
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            approval_id=str(uuid.uuid4()),
            tool_name=tool_name,
            input_data=input_data,
            requested_at=time.time(),
            requested_by=requested_by,
            interface=self.interface,
        )
        self.pending[req.approval_id] = req
        return req

    def resolve(
        self,
        approval_id: str,
        *,
        allowed: bool,
        updated_input: dict | None = None,
        reason: str | None = None,
        decided_by: str = "unknown",
    ) -> bool:
        req = self.pending.get(approval_id)
        if req is None or req.future.done():
            return False
        req.future.set_result(
            ApprovalResult(
                allowed=allowed,
                updated_input=updated_input,
                reason=reason,
                decided_by=decided_by,
            )
        )
        return True

    async def request(self, req: ApprovalRequest) -> ApprovalResult:
        # Caller is expected to have invoked new_request(); but allow direct
        # invocation by registering on the fly.
        if req.approval_id not in self.pending:
            self.pending[req.approval_id] = req
        try:
            return await asyncio.wait_for(req.future, timeout=self.timeout_s)
        except asyncio.TimeoutError:
            return ApprovalResult(
                allowed=False,
                reason=f"Approval timed out after {self.timeout_s}s.",
                decided_by="timeout",
            )
        finally:
            self.pending.pop(req.approval_id, None)


# ---- read-only registry ----------------------------------------------------

_READ_ONLY_TOOLS: set[str] = set()
_REGISTERED_TOOLS: set[str] = set()


def register_tool(name: str, *, read_only: bool) -> None:
    """Record a tool's read-only classification at import time."""
    _REGISTERED_TOOLS.add(name)
    if read_only:
        _READ_ONLY_TOOLS.add(name)


def is_read_only(tool_name: str) -> bool:
    """Return True if the given fully-qualified tool name is read-only."""
    # SDK exposes our @tool functions as `mcp__<server>__<tool>`. We registered
    # by the bare name; accept either form.
    if tool_name in _READ_ONLY_TOOLS:
        return True
    if tool_name.startswith("mcp__"):
        bare = tool_name.rsplit("__", 1)[-1]
        return bare in _READ_ONLY_TOOLS
    return False


def known_tools() -> set[str]:
    """All registered tool bare-names; used by the build-time test."""
    return set(_REGISTERED_TOOLS)


def read_only_tools() -> set[str]:
    return set(_READ_ONLY_TOOLS)


# ---- can_use_tool factory --------------------------------------------------

# We avoid a hard import of claude_agent_sdk at module load so the rest of
# the package (and our unit tests) work even when the SDK is not installed
# in the current environment.
def _allow_result(updated_input: dict | None = None):
    from claude_agent_sdk import PermissionResultAllow  # type: ignore

    return PermissionResultAllow(updated_input=updated_input or {})


def _deny_result(message: str):
    from claude_agent_sdk import PermissionResultDeny  # type: ignore

    return PermissionResultDeny(message=message, interrupt=False)


CanUseTool = Callable[[str, dict, Any], Awaitable[Any]]


def make_can_use_tool(
    broker: ApprovalBroker,
    *,
    read_only_mode: bool,
) -> CanUseTool:
    """Build the SDK's can_use_tool callback.

    Decision order:
      1. Tool marked read-only via @tool annotation -> allow.
      2. read_only_mode flag is set -> deny with explanation.
      3. Otherwise delegate to the broker.
    """

    async def can_use_tool(tool_name: str, input_data: dict, context):
        requested_at = time.time()

        if is_read_only(tool_name):
            audit.log_decision(
                tool_name=tool_name,
                input_data=input_data,
                decision="auto-allow-readonly",
                decided_by="system",
                interface=broker.interface,
                requested_at=requested_at,
            )
            return _allow_result()

        if read_only_mode:
            msg = (
                "Read-only mode is active; mutating tool calls are disabled. "
                "Describe the intended change instead."
            )
            audit.log_decision(
                tool_name=tool_name,
                input_data=input_data,
                decision="deny-readonly-mode",
                decided_by="system",
                interface=broker.interface,
                requested_at=requested_at,
                reason=msg,
            )
            return _deny_result(msg)

        req = (
            broker.new_request(tool_name=tool_name, input_data=input_data)
            if isinstance(broker, FutureBackedBroker)
            else ApprovalRequest(
                approval_id=str(uuid.uuid4()),
                tool_name=tool_name,
                input_data=input_data,
                requested_at=requested_at,
                interface=broker.interface,
            )
        )
        result = await broker.request(req)

        audit.log_decision(
            tool_name=tool_name,
            input_data=input_data,
            decision="allow" if result.allowed else "deny",
            decided_by=result.decided_by,
            interface=broker.interface,
            requested_at=requested_at,
            reason=result.reason,
        )

        if result.allowed:
            return _allow_result(result.updated_input)
        return _deny_result(result.reason or "Mutation denied by approver.")

    return can_use_tool
