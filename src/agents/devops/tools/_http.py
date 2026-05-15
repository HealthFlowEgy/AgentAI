"""Shared async HTTP client factory for DevOps tools."""
from __future__ import annotations

import httpx

GITHUB_API = "https://api.github.com"
DIGITALOCEAN_API = "https://api.digitalocean.com/v2"

_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)


def github_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=GITHUB_API,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "healthflow-devops-agent/0.1",
        },
        timeout=_DEFAULT_TIMEOUT,
    )


def do_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=DIGITALOCEAN_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "healthflow-devops-agent/0.1",
        },
        timeout=_DEFAULT_TIMEOUT,
    )


def text_block(text: str) -> dict:
    """Wrap a string into the SDK's tool-result content shape."""
    return {"content": [{"type": "text", "text": text}]}


def json_block(data) -> dict:
    """Wrap arbitrary JSON-serializable data as a text block (pretty)."""
    import json

    return text_block(json.dumps(data, indent=2, default=str))
