"""Build and run the DevOps engineering agent.

The Claude Agent SDK is imported lazily so the rest of the package — and
the unit tests for the permission gate — don't require it at import time.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from src.agents.devops.permissions import (
    ApprovalBroker,
    AutoDenyBroker,
    make_can_use_tool,
)
from src.agents.devops.prompts import render_prompt

logger = logging.getLogger(__name__)


def _validate_settings() -> None:
    from config.settings import settings

    missing = [
        name
        for name, val in (
            ("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY),
            ("GITHUB_TOKEN", settings.GITHUB_TOKEN),
            ("DIGITALOCEAN_TOKEN", settings.DIGITALOCEAN_TOKEN),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "DevOps agent cannot start; missing required env vars: "
            + ", ".join(missing)
        )


def build_agent_options(
    *,
    broker: ApprovalBroker | None = None,
    read_only_mode: bool | None = None,
) -> Any:
    """Construct ``ClaudeAgentOptions`` for one DevOps session."""
    from claude_agent_sdk import ClaudeAgentOptions  # type: ignore

    from config.settings import settings
    from src.agents.devops.tools import build_mcp_servers

    _validate_settings()

    ro = settings.DEVOPS_READ_ONLY_MODE if read_only_mode is None else read_only_mode
    used_broker = broker or AutoDenyBroker()

    return ClaudeAgentOptions(
        system_prompt=render_prompt(read_only=ro),
        mcp_servers=build_mcp_servers(),
        can_use_tool=make_can_use_tool(used_broker, read_only_mode=ro),
        model=settings.DEVOPS_AGENT_MODEL,
        max_turns=settings.DEVOPS_MAX_TURNS,
        env={"ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY or ""},
    )


@asynccontextmanager
async def open_session(
    *,
    broker: ApprovalBroker | None = None,
    read_only_mode: bool | None = None,
) -> AsyncIterator[Any]:
    """Async context manager yielding a connected ``ClaudeSDKClient``."""
    from claude_agent_sdk import ClaudeSDKClient  # type: ignore

    options = build_agent_options(broker=broker, read_only_mode=read_only_mode)
    async with ClaudeSDKClient(options=options) as client:
        yield client


async def run_one_shot(
    prompt: str,
    *,
    broker: ApprovalBroker | None = None,
    read_only_mode: bool | None = None,
) -> AsyncIterator[Any]:
    """Yield response messages for a single prompt, then disconnect.

    The caller is expected to consume the iterator (e.g. to print tokens
    or push them onto an SSE stream) and then break out.
    """
    async with open_session(broker=broker, read_only_mode=read_only_mode) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            yield msg
