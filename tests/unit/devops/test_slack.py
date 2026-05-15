"""Tests for the Slack DevOps endpoints."""
from __future__ import annotations

import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.settings import settings
from src.agents.devops.interfaces import api as devops_api


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_SIGNING_SECRET", None, raising=False)
    monkeypatch.setattr(settings, "DEVOPS_SLACK_APPROVERS", ["U_APPROVER"], raising=False)
    a = FastAPI()
    a.include_router(devops_api.router)
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def test_slack_url_verification(client):
    r = client.post(
        "/api/devops/slack/events",
        json={"type": "url_verification", "challenge": "abc123"},
    )
    assert r.status_code == 200
    assert r.json() == {"challenge": "abc123"}


def test_slack_interactive_resolves_approval(client):
    broker = devops_api.broker
    req = broker.new_request(
        tool_name="gh_create_pr",
        input_data={"owner": "o", "repo": "r", "title": "x", "head": "h"},
    )
    payload = {
        "user": {"id": "U_APPROVER"},
        "actions": [
            {
                "block_id": req.approval_id,
                "value": f"{req.approval_id}:allow",
                "action_id": "approve",
            }
        ],
    }
    r = client.post(
        "/api/devops/slack/interactive",
        data={"payload": json.dumps(payload)},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert req.future.done()
    assert req.future.result().allowed is True
    broker.pending.pop(req.approval_id, None)


def test_slack_interactive_rejects_non_approver(client):
    broker = devops_api.broker
    req = broker.new_request(
        tool_name="gh_create_pr",
        input_data={"owner": "o", "repo": "r", "title": "x", "head": "h"},
    )
    payload = {
        "user": {"id": "U_RANDO"},
        "actions": [{"block_id": req.approval_id, "value": f"{req.approval_id}:allow"}],
    }
    r = client.post(
        "/api/devops/slack/interactive",
        data={"payload": json.dumps(payload)},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 403
    # Future should still be pending; clean up.
    assert not req.future.done()
    broker.pending.pop(req.approval_id, None)
