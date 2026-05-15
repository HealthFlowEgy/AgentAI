"""Smoke tests for GitHub tools using respx to fake the API."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.agents.devops.tools import github_tools


@pytest.mark.asyncio
async def test_gh_list_repos_parses_payload():
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://api.github.com/user/repos").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"full_name": "octocat/hello", "private": False, "default_branch": "main"},
                    {"full_name": "octocat/secret", "private": True, "default_branch": "main"},
                ],
            )
        )
        out = await github_tools.gh_list_repos({})

    body = out["content"][0]["text"]
    parsed = json.loads(body)
    assert parsed[0]["full_name"] == "octocat/hello"
    assert parsed[1]["private"] is True


@pytest.mark.asyncio
async def test_gh_create_pr_posts_correct_body():
    captured = {}

    def _capture(request: httpx.Request):
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            201,
            json={"number": 42, "html_url": "https://github.com/o/r/pull/42"},
        )

    with respx.mock as mock:
        mock.post("https://api.github.com/repos/o/r/pulls").mock(side_effect=_capture)
        out = await github_tools.gh_create_pr(
            {"owner": "o", "repo": "r", "title": "T", "head": "h", "base": "main", "body": "B"}
        )

    assert captured["body"]["title"] == "T"
    assert captured["body"]["head"] == "h"
    assert captured["body"]["base"] == "main"
    assert "PR #42" in out["content"][0]["text"]


@pytest.mark.asyncio
async def test_gh_merge_pr_calls_put():
    with respx.mock as mock:
        mock.put("https://api.github.com/repos/o/r/pulls/7/merge").mock(
            return_value=httpx.Response(200, json={"merged": True, "sha": "deadbeef"})
        )
        out = await github_tools.gh_merge_pr(
            {"owner": "o", "repo": "r", "number": 7, "merge_method": "squash"}
        )
    assert "Merged PR #7" in out["content"][0]["text"]
