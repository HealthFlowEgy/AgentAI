"""Higher-level dev-environment workflow tools.

v1 ships only the read-only inspection tools. ``provision_preview`` and
``teardown_preview`` are intentionally deferred to v2; the agent is expected
to compose ``gh_*`` and ``do_*`` calls in the meantime, each gated by an
individual approval.
"""
from __future__ import annotations

from src.agents.devops.tools import devops_tool
from src.agents.devops.tools._http import do_client, github_client, json_block


def _gh_token() -> str:
    from config.settings import settings

    if not settings.GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set.")
    return settings.GITHUB_TOKEN


def _do_token() -> str:
    from config.settings import settings

    if not settings.DIGITALOCEAN_TOKEN:
        raise RuntimeError("DIGITALOCEAN_TOKEN is not set.")
    return settings.DIGITALOCEAN_TOKEN


@devops_tool(
    server="devenv",
    name="devenv_describe_pr",
    description=(
        "Combine PR metadata, head ref, base ref, and a list of changed "
        "files into a compact summary suitable for planning a preview env."
    ),
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
async def devenv_describe_pr(args: dict) -> dict:
    async with github_client(_gh_token()) as c:
        pr = await c.get(f"/repos/{args['owner']}/{args['repo']}/pulls/{args['number']}")
        pr.raise_for_status()
        files = await c.get(
            f"/repos/{args['owner']}/{args['repo']}/pulls/{args['number']}/files"
        )
        files.raise_for_status()
        pr_data = pr.json()
    summary = {
        "number": pr_data["number"],
        "title": pr_data["title"],
        "state": pr_data["state"],
        "head": pr_data["head"]["ref"],
        "head_sha": pr_data["head"]["sha"],
        "base": pr_data["base"]["ref"],
        "mergeable": pr_data.get("mergeable"),
        "changed_files": [f["filename"] for f in files.json()],
    }
    return json_block(summary)


@devops_tool(
    server="devenv",
    name="devenv_status",
    description=(
        "Report the deployment status of a candidate preview environment "
        "by app id, returning the most recent deployment phase and live URL."
    ),
    input_schema={
        "type": "object",
        "properties": {"app_id": {"type": "string"}},
        "required": ["app_id"],
    },
    read_only=True,
)
async def devenv_status(args: dict) -> dict:
    async with do_client(_do_token()) as c:
        app = await c.get(f"/apps/{args['app_id']}")
        app.raise_for_status()
        a = app.json().get("app", {})
        active = a.get("active_deployment") or {}
    summary = {
        "app_id": args["app_id"],
        "name": a.get("spec", {}).get("name"),
        "live_url": a.get("live_url"),
        "deployment_id": active.get("id"),
        "phase": active.get("phase"),
        "updated_at": active.get("updated_at"),
    }
    return json_block(summary)
