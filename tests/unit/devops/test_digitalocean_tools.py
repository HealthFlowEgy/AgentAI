"""Smoke tests for DigitalOcean tools using respx."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.agents.devops.tools import digitalocean_tools as do_tools


@pytest.mark.asyncio
async def test_do_list_droplets_parses_payload():
    with respx.mock as mock:
        mock.get("https://api.digitalocean.com/v2/droplets").mock(
            return_value=httpx.Response(
                200,
                json={
                    "droplets": [
                        {
                            "id": 1,
                            "name": "web-1",
                            "status": "active",
                            "region": {"slug": "nyc3"},
                            "size_slug": "s-1vcpu-1gb",
                            "networks": {
                                "v4": [{"type": "public", "ip_address": "203.0.113.1"}]
                            },
                        }
                    ]
                },
            )
        )
        out = await do_tools.do_list_droplets({})

    parsed = json.loads(out["content"][0]["text"])
    assert parsed[0]["name"] == "web-1"
    assert parsed[0]["ip"] == "203.0.113.1"


@pytest.mark.asyncio
async def test_do_create_droplet_posts_correct_body():
    captured = {}

    def _capture(request: httpx.Request):
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            202,
            json={"droplet": {"id": 999, "name": captured["body"]["name"]}},
        )

    with respx.mock as mock:
        mock.post("https://api.digitalocean.com/v2/droplets").mock(side_effect=_capture)
        out = await do_tools.do_create_droplet(
            {
                "name": "preview-pr-42",
                "region": "fra1",
                "size": "s-2vcpu-2gb",
                "image": "ubuntu-22-04-x64",
                "tags": ["preview"],
            }
        )

    assert captured["body"]["region"] == "fra1"
    assert captured["body"]["tags"] == ["preview"]
    assert "preview-pr-42" in out["content"][0]["text"]


@pytest.mark.asyncio
async def test_do_destroy_droplet_uses_delete():
    with respx.mock as mock:
        mock.delete("https://api.digitalocean.com/v2/droplets/123").mock(
            return_value=httpx.Response(204)
        )
        out = await do_tools.do_destroy_droplet({"droplet_id": 123})
    assert "Destroyed droplet 123" in out["content"][0]["text"]
