"""Live integration smoke tests for the DevOps agent.

Skipped by default. To run:

    RUN_DEVOPS_LIVE=1 \\
    ANTHROPIC_API_KEY=... \\
    GITHUB_TOKEN=... \\
    DIGITALOCEAN_TOKEN=... \\
    DEVOPS_LIVE_GH_OWNER=<your-org-or-user> \\
    DEVOPS_LIVE_GH_REPO=<repo-that-the-token-can-read> \\
    python -m pytest tests/integration/devops/test_smoke.py -v \\
      --rootdir=tests/integration/devops --confcutdir=tests/integration/devops -o "addopts="

These tests hit real APIs:
  - GitHub:       reads only (gh_list_repos, gh_list_branches if a repo is given)
  - DigitalOcean: reads only (do_list_droplets, do_list_apps)
  - Claude:       NOT exercised here — these tests exercise only the tool layer
                  so they don't burn agent tokens. To smoke the full agent loop,
                  point the CLI at a real ANTHROPIC_API_KEY and prompt it.

The tests never mutate state. They confirm credentials are valid and that
the tool surface still maps cleanly to live API responses.
"""
from __future__ import annotations

import json
import os

import pytest

LIVE = os.environ.get("RUN_DEVOPS_LIVE") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="set RUN_DEVOPS_LIVE=1 to enable live DevOps smoke tests",
)


@pytest.fixture(scope="session")
def _env_check():
    missing = [
        name
        for name in ("GITHUB_TOKEN", "DIGITALOCEAN_TOKEN")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(f"missing required env vars: {', '.join(missing)}")
    return None


@pytest.mark.asyncio
async def test_live_gh_list_repos_returns_something(_env_check):
    from src.agents.devops.tools import github_tools

    out = await github_tools.gh_list_repos({"per_page": 5})
    parsed = json.loads(out["content"][0]["text"])
    assert isinstance(parsed, list)
    # At least one repo is reachable with the supplied token, OR the token
    # is scoped to zero repos — either way the call must succeed.
    for repo in parsed:
        assert "full_name" in repo


@pytest.mark.asyncio
async def test_live_gh_list_branches_if_repo_configured(_env_check):
    from src.agents.devops.tools import github_tools

    owner = os.environ.get("DEVOPS_LIVE_GH_OWNER")
    repo = os.environ.get("DEVOPS_LIVE_GH_REPO")
    if not owner or not repo:
        pytest.skip("set DEVOPS_LIVE_GH_OWNER and DEVOPS_LIVE_GH_REPO to run")
    out = await github_tools.gh_list_branches({"owner": owner, "repo": repo})
    parsed = json.loads(out["content"][0]["text"])
    assert isinstance(parsed, list)
    assert any("name" in b and "sha" in b for b in parsed)


@pytest.mark.asyncio
async def test_live_do_list_droplets(_env_check):
    from src.agents.devops.tools import digitalocean_tools

    out = await digitalocean_tools.do_list_droplets({})
    parsed = json.loads(out["content"][0]["text"])
    assert isinstance(parsed, list)
    for d in parsed:
        # Shape contract — every droplet returned has these keys.
        for k in ("id", "name", "status", "region"):
            assert k in d


@pytest.mark.asyncio
async def test_live_do_list_apps(_env_check):
    from src.agents.devops.tools import digitalocean_tools

    out = await digitalocean_tools.do_list_apps({})
    parsed = json.loads(out["content"][0]["text"])
    assert isinstance(parsed, list)
    for a in parsed:
        assert "id" in a and "name" in a


@pytest.mark.asyncio
async def test_live_read_only_mode_denies_mutation(_env_check, monkeypatch):
    """End-to-end check that the permission gate rejects a mutating tool
    under read-only mode, without actually hitting the upstream API."""
    from src.agents.devops.permissions import AutoAllowBroker, make_can_use_tool

    can_use = make_can_use_tool(AutoAllowBroker(), read_only_mode=True)
    result = await can_use(
        "gh_create_branch",
        {"owner": "x", "repo": "y", "new_branch": "z"},
        None,
    )
    assert result.__class__.__name__ == "PermissionResultDeny"
