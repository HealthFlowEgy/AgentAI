"""GitHub tools for the DevOps agent.

Uses the GitHub REST API directly via httpx to keep the dependency
surface narrow and to make unit testing with respx straightforward.
"""
from __future__ import annotations

import base64
from typing import Any

from src.agents.devops.tools import devops_tool
from src.agents.devops.tools._http import github_client, json_block, text_block


def _token() -> str:
    from config.settings import settings

    if not settings.GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN is not set; the GitHub tools cannot be used."
        )
    return settings.GITHUB_TOKEN


# ---- Read-only -------------------------------------------------------------


@devops_tool(
    server="github",
    name="gh_list_repos",
    description="List repositories accessible to the configured GitHub token.",
    input_schema={
        "type": "object",
        "properties": {
            "visibility": {
                "type": "string",
                "enum": ["all", "public", "private"],
                "default": "all",
            },
            "per_page": {"type": "integer", "default": 30, "maximum": 100},
        },
    },
    read_only=True,
)
async def gh_list_repos(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(
            "/user/repos",
            params={
                "visibility": args.get("visibility", "all"),
                "per_page": args.get("per_page", 30),
            },
        )
        r.raise_for_status()
        repos = [
            {"full_name": x["full_name"], "private": x["private"], "default_branch": x.get("default_branch")}
            for x in r.json()
        ]
        return json_block(repos)


@devops_tool(
    server="github",
    name="gh_get_repo",
    description="Get metadata for a specific repository.",
    input_schema={
        "type": "object",
        "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
        "required": ["owner", "repo"],
    },
    read_only=True,
)
async def gh_get_repo(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(f"/repos/{args['owner']}/{args['repo']}")
        r.raise_for_status()
        return json_block(r.json())


@devops_tool(
    server="github",
    name="gh_list_branches",
    description="List branches for a repository.",
    input_schema={
        "type": "object",
        "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
        "required": ["owner", "repo"],
    },
    read_only=True,
)
async def gh_list_branches(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(f"/repos/{args['owner']}/{args['repo']}/branches")
        r.raise_for_status()
        return json_block([{"name": b["name"], "sha": b["commit"]["sha"]} for b in r.json()])


@devops_tool(
    server="github",
    name="gh_list_prs",
    description="List pull requests for a repository.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
        },
        "required": ["owner", "repo"],
    },
    read_only=True,
)
async def gh_list_prs(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(
            f"/repos/{args['owner']}/{args['repo']}/pulls",
            params={"state": args.get("state", "open")},
        )
        r.raise_for_status()
        prs = [
            {"number": p["number"], "title": p["title"], "state": p["state"], "user": p["user"]["login"]}
            for p in r.json()
        ]
        return json_block(prs)


@devops_tool(
    server="github",
    name="gh_get_pr",
    description="Get a pull request by number, including head/base refs and mergeability.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "number": {"type": "integer"},
        },
        "required": ["owner", "repo", "number"],
    },
    read_only=True,
)
async def gh_get_pr(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(f"/repos/{args['owner']}/{args['repo']}/pulls/{args['number']}")
        r.raise_for_status()
        return json_block(r.json())


@devops_tool(
    server="github",
    name="gh_list_issues",
    description="List issues for a repository (excludes PRs).",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
        },
        "required": ["owner", "repo"],
    },
    read_only=True,
)
async def gh_list_issues(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(
            f"/repos/{args['owner']}/{args['repo']}/issues",
            params={"state": args.get("state", "open")},
        )
        r.raise_for_status()
        issues = [
            {"number": i["number"], "title": i["title"], "state": i["state"]}
            for i in r.json()
            if "pull_request" not in i
        ]
        return json_block(issues)


@devops_tool(
    server="github",
    name="gh_list_workflow_runs",
    description="List recent GitHub Actions workflow runs.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "per_page": {"type": "integer", "default": 10},
        },
        "required": ["owner", "repo"],
    },
    read_only=True,
)
async def gh_list_workflow_runs(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(
            f"/repos/{args['owner']}/{args['repo']}/actions/runs",
            params={"per_page": args.get("per_page", 10)},
        )
        r.raise_for_status()
        data = r.json()
        runs = [
            {
                "id": run["id"],
                "name": run["name"],
                "status": run["status"],
                "conclusion": run["conclusion"],
                "head_branch": run["head_branch"],
            }
            for run in data.get("workflow_runs", [])
        ]
        return json_block(runs)


@devops_tool(
    server="github",
    name="gh_get_workflow_run_logs",
    description="Fetch the logs URL for a specific workflow run (returns redirect URL).",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "run_id": {"type": "integer"},
        },
        "required": ["owner", "repo", "run_id"],
    },
    read_only=True,
)
async def gh_get_workflow_run_logs(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.get(
            f"/repos/{args['owner']}/{args['repo']}/actions/runs/{args['run_id']}/logs",
            follow_redirects=False,
        )
        if r.status_code in (301, 302, 307):
            return text_block(f"Logs available at: {r.headers.get('location')}")
        r.raise_for_status()
        return text_block(f"Logs ({len(r.content)} bytes) — fetch with the URL above.")


# ---- Mutating --------------------------------------------------------------


@devops_tool(
    server="github",
    name="gh_create_branch",
    description="Create a new branch from a source branch's HEAD.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "new_branch": {"type": "string"},
            "from_branch": {"type": "string", "default": "main"},
        },
        "required": ["owner", "repo", "new_branch"],
    },
    read_only=False,
)
async def gh_create_branch(args: dict) -> dict:
    async with github_client(_token()) as c:
        ref = await c.get(
            f"/repos/{args['owner']}/{args['repo']}/git/ref/heads/{args.get('from_branch', 'main')}"
        )
        ref.raise_for_status()
        sha = ref.json()["object"]["sha"]
        r = await c.post(
            f"/repos/{args['owner']}/{args['repo']}/git/refs",
            json={"ref": f"refs/heads/{args['new_branch']}", "sha": sha},
        )
        r.raise_for_status()
        return text_block(f"Created branch {args['new_branch']} at {sha[:7]}.")


@devops_tool(
    server="github",
    name="gh_create_pr",
    description="Open a pull request.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "head": {"type": "string"},
            "base": {"type": "string", "default": "main"},
            "body": {"type": "string", "default": ""},
            "draft": {"type": "boolean", "default": False},
        },
        "required": ["owner", "repo", "title", "head"],
    },
    read_only=False,
)
async def gh_create_pr(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.post(
            f"/repos/{args['owner']}/{args['repo']}/pulls",
            json={
                "title": args["title"],
                "head": args["head"],
                "base": args.get("base", "main"),
                "body": args.get("body", ""),
                "draft": args.get("draft", False),
            },
        )
        r.raise_for_status()
        pr = r.json()
        return text_block(f"Opened PR #{pr['number']}: {pr['html_url']}")


@devops_tool(
    server="github",
    name="gh_merge_pr",
    description="Merge a pull request.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "number": {"type": "integer"},
            "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"], "default": "squash"},
        },
        "required": ["owner", "repo", "number"],
    },
    read_only=False,
)
async def gh_merge_pr(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.put(
            f"/repos/{args['owner']}/{args['repo']}/pulls/{args['number']}/merge",
            json={"merge_method": args.get("merge_method", "squash")},
        )
        r.raise_for_status()
        return text_block(f"Merged PR #{args['number']}.")


@devops_tool(
    server="github",
    name="gh_close_pr",
    description="Close a pull request without merging.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "number": {"type": "integer"},
        },
        "required": ["owner", "repo", "number"],
    },
    read_only=False,
)
async def gh_close_pr(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.patch(
            f"/repos/{args['owner']}/{args['repo']}/pulls/{args['number']}",
            json={"state": "closed"},
        )
        r.raise_for_status()
        return text_block(f"Closed PR #{args['number']}.")


@devops_tool(
    server="github",
    name="gh_create_issue",
    description="Create a new issue.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string", "default": ""},
            "labels": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["owner", "repo", "title"],
    },
    read_only=False,
)
async def gh_create_issue(args: dict) -> dict:
    async with github_client(_token()) as c:
        payload: dict[str, Any] = {"title": args["title"], "body": args.get("body", "")}
        if "labels" in args:
            payload["labels"] = args["labels"]
        r = await c.post(f"/repos/{args['owner']}/{args['repo']}/issues", json=payload)
        r.raise_for_status()
        issue = r.json()
        return text_block(f"Created issue #{issue['number']}: {issue['html_url']}")


@devops_tool(
    server="github",
    name="gh_comment_issue",
    description="Add a comment to an issue or PR.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "number": {"type": "integer"},
            "body": {"type": "string"},
        },
        "required": ["owner", "repo", "number", "body"],
    },
    read_only=False,
)
async def gh_comment_issue(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.post(
            f"/repos/{args['owner']}/{args['repo']}/issues/{args['number']}/comments",
            json={"body": args["body"]},
        )
        r.raise_for_status()
        return text_block(f"Posted comment on #{args['number']}.")


@devops_tool(
    server="github",
    name="gh_dispatch_workflow",
    description="Trigger a workflow_dispatch event for a workflow file.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "workflow_file": {"type": "string", "description": "e.g. ci.yml"},
            "ref": {"type": "string", "default": "main"},
            "inputs": {"type": "object", "default": {}},
        },
        "required": ["owner", "repo", "workflow_file"],
    },
    read_only=False,
)
async def gh_dispatch_workflow(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.post(
            f"/repos/{args['owner']}/{args['repo']}/actions/workflows/{args['workflow_file']}/dispatches",
            json={"ref": args.get("ref", "main"), "inputs": args.get("inputs", {})},
        )
        r.raise_for_status()
        return text_block(f"Dispatched {args['workflow_file']} on {args.get('ref', 'main')}.")


@devops_tool(
    server="github",
    name="gh_rerun_workflow",
    description="Re-run a failed workflow run.",
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "run_id": {"type": "integer"},
        },
        "required": ["owner", "repo", "run_id"],
    },
    read_only=False,
)
async def gh_rerun_workflow(args: dict) -> dict:
    async with github_client(_token()) as c:
        r = await c.post(
            f"/repos/{args['owner']}/{args['repo']}/actions/runs/{args['run_id']}/rerun"
        )
        r.raise_for_status()
        return text_block(f"Re-running run {args['run_id']}.")


@devops_tool(
    server="github",
    name="gh_set_repo_secret",
    description=(
        "Create or update a repository Actions secret. The value is sealed "
        "with the repo's libsodium public key before transport."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "name": {"type": "string", "description": "Secret name"},
            "value": {"type": "string", "description": "Plaintext secret value"},
        },
        "required": ["owner", "repo", "name", "value"],
    },
    read_only=False,
)
async def gh_set_repo_secret(args: dict) -> dict:
    from nacl import encoding, public  # type: ignore

    async with github_client(_token()) as c:
        pk = await c.get(f"/repos/{args['owner']}/{args['repo']}/actions/secrets/public-key")
        pk.raise_for_status()
        pk_data = pk.json()
        sealed_box = public.SealedBox(
            public.PublicKey(pk_data["key"].encode("utf-8"), encoding.Base64Encoder())
        )
        encrypted = sealed_box.encrypt(args["value"].encode("utf-8"))
        encrypted_value = base64.b64encode(encrypted).decode("utf-8")
        r = await c.put(
            f"/repos/{args['owner']}/{args['repo']}/actions/secrets/{args['name']}",
            json={"encrypted_value": encrypted_value, "key_id": pk_data["key_id"]},
        )
        r.raise_for_status()
        return text_block(f"Stored secret {args['name']} on {args['owner']}/{args['repo']}.")
