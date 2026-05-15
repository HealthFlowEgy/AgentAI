"""Tests for the DevOps permission gate."""
from __future__ import annotations

import asyncio

import pytest

# Import side-effects: tool modules register themselves on import.
from src.agents.devops.tools import github_tools, digitalocean_tools, devenv_tools  # noqa: F401
from src.agents.devops.permissions import (
    AutoAllowBroker,
    FutureBackedBroker,
    is_read_only,
    known_tools,
    make_can_use_tool,
    read_only_tools,
)


def test_every_registered_tool_has_explicit_read_only_classification():
    # If a new @devops_tool is added without setting `read_only`, the
    # decorator forces a value, so the registry should always partition
    # cleanly: every tool is either in read_only_tools() or it is not.
    assert known_tools(), "no tools registered"
    for name in known_tools():
        # Pure sanity: every registered tool should resolve consistently.
        assert is_read_only(name) in (True, False)


@pytest.mark.asyncio
async def test_read_only_tool_is_auto_allowed():
    can_use = make_can_use_tool(AutoAllowBroker(), read_only_mode=False)
    result = await can_use("gh_list_repos", {}, None)
    assert result.__class__.__name__ == "PermissionResultAllow"


@pytest.mark.asyncio
async def test_mutating_tool_denied_in_read_only_mode():
    can_use = make_can_use_tool(AutoAllowBroker(), read_only_mode=True)
    result = await can_use("gh_create_pr", {"title": "x"}, None)
    assert result.__class__.__name__ == "PermissionResultDeny"
    assert "read-only mode" in result.message.lower()


@pytest.mark.asyncio
async def test_mutating_tool_delegates_to_broker_allow():
    broker = FutureBackedBroker(interface="test", timeout_s=5)

    async def caller():
        return await make_can_use_tool(broker, read_only_mode=False)(
            "gh_create_branch",
            {"owner": "o", "repo": "r", "new_branch": "x"},
            None,
        )

    task = asyncio.create_task(caller())
    # Wait until the broker has a pending request, then resolve it.
    for _ in range(50):
        if broker.pending:
            break
        await asyncio.sleep(0.01)
    approval_id = next(iter(broker.pending))
    assert broker.resolve(approval_id, allowed=True, decided_by="test")
    result = await task
    assert result.__class__.__name__ == "PermissionResultAllow"


@pytest.mark.asyncio
async def test_mutating_tool_delegates_to_broker_deny():
    broker = FutureBackedBroker(interface="test", timeout_s=5)

    async def caller():
        return await make_can_use_tool(broker, read_only_mode=False)(
            "gh_merge_pr",
            {"owner": "o", "repo": "r", "number": 1},
            None,
        )

    task = asyncio.create_task(caller())
    for _ in range(50):
        if broker.pending:
            break
        await asyncio.sleep(0.01)
    approval_id = next(iter(broker.pending))
    broker.resolve(approval_id, allowed=False, reason="nope", decided_by="test")
    result = await task
    assert result.__class__.__name__ == "PermissionResultDeny"
    assert result.message == "nope"


@pytest.mark.asyncio
async def test_broker_timeout_results_in_deny():
    broker = FutureBackedBroker(interface="test", timeout_s=0)
    result = await make_can_use_tool(broker, read_only_mode=False)(
        "gh_create_issue", {"owner": "o", "repo": "r", "title": "x"}, None
    )
    assert result.__class__.__name__ == "PermissionResultDeny"
    assert "timed out" in result.message.lower()


def test_known_tools_includes_expected_names():
    names = known_tools()
    assert "gh_list_repos" in names
    assert "gh_create_pr" in names
    assert "do_list_droplets" in names
    assert "do_create_droplet" in names
    assert "devenv_describe_pr" in names


def test_read_only_classification_matches_expectations():
    ro = read_only_tools()
    # Sample of read-only tools
    for name in ("gh_list_repos", "gh_get_pr", "do_list_droplets", "devenv_status"):
        assert name in ro, f"{name} should be read-only"
    # Sample of mutating tools
    for name in ("gh_create_pr", "gh_merge_pr", "do_create_droplet", "do_destroy_droplet"):
        assert name not in ro, f"{name} should be mutating"
