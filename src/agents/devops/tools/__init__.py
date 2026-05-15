"""DevOps tool registry.

Each provider module declares its tools with the local ``devops_tool``
decorator (re-exported here). At MCP-server build time we wrap the
collected callables with the real ``claude_agent_sdk.tool`` decorator and
group them into ``create_sdk_mcp_server`` configs.

Defining tools through the local decorator keeps them importable in
environments where the Claude Agent SDK isn't installed (e.g. CI for the
non-DevOps parts of the repo, unit tests for the permission gate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from src.agents.devops.permissions import register_tool


@dataclass
class DevOpsTool:
    """Local representation of a tool before SDK wiring."""

    name: str
    description: str
    input_schema: dict
    handler: Callable
    read_only: bool


_REGISTRY: dict[str, list[DevOpsTool]] = {"github": [], "do": [], "devenv": []}


def devops_tool(
    *,
    server: str,
    name: str,
    description: str,
    input_schema: dict,
    read_only: bool,
):
    """Register a DevOps tool. Decorate an async ``def`` returning ``dict``.

    The decorated function returns a dict with optional ``content`` (list of
    text/data blocks) compatible with what the SDK ``@tool`` returns.
    """

    if server not in _REGISTRY:
        raise ValueError(f"unknown DevOps tool server: {server!r}")

    def decorator(fn: Callable) -> Callable:
        _REGISTRY[server].append(
            DevOpsTool(
                name=name,
                description=description,
                input_schema=input_schema,
                handler=fn,
                read_only=read_only,
            )
        )
        register_tool(name, read_only=read_only)
        return fn

    return decorator


def registered_tools(server: str) -> list[DevOpsTool]:
    return list(_REGISTRY[server])


def all_servers() -> Iterable[str]:
    return _REGISTRY.keys()


def build_mcp_servers() -> dict[str, Any]:
    """Wrap each registered tool with ``claude_agent_sdk.tool`` and return
    a mapping suitable for ``ClaudeAgentOptions(mcp_servers=...)``.
    """
    from claude_agent_sdk import (  # type: ignore
        ToolAnnotations,
        create_sdk_mcp_server,
        tool,
    )

    # Trigger registration side-effects.
    from src.agents.devops.tools import (  # noqa: F401  (registration only)
        github_tools,
        digitalocean_tools,
        devenv_tools,
    )

    servers: dict[str, Any] = {}
    for server_name in _REGISTRY:
        wrapped = []
        for spec in _REGISTRY[server_name]:
            wrapped.append(
                tool(
                    spec.name,
                    spec.description,
                    spec.input_schema,
                    annotations=ToolAnnotations(readOnlyHint=spec.read_only),
                )(spec.handler)
            )
        servers[server_name] = create_sdk_mcp_server(
            name=f"devops-{server_name}",
            version="0.1.0",
            tools=wrapped,
        )
    return servers
