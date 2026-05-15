"""Tests for the DevOps FastAPI router (auth-bypassed for unit scope)."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents.devops.interfaces import api as devops_api


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(devops_api.router)
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


def test_health(client):
    r = client.get("/api/devops/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_approve_unknown_id_404(client):
    r = client.post(
        "/api/devops/approve",
        json={"approval_id": "does-not-exist", "decision": "allow"},
    )
    assert r.status_code == 404


def test_approve_resolves_pending_request(client):
    """Push a fake pending approval, then resolve it via the endpoint."""
    broker = devops_api.broker
    req = broker.new_request(
        tool_name="gh_create_branch",
        input_data={"owner": "o", "repo": "r", "new_branch": "x"},
    )

    # The approval list endpoint should reflect the pending request.
    listed = client.get("/api/devops/approvals").json()
    assert any(item["approval_id"] == req.approval_id for item in listed)

    # Resolve via /approve.
    r = client.post(
        "/api/devops/approve",
        json={"approval_id": req.approval_id, "decision": "allow"},
    )
    assert r.status_code == 200
    assert r.json() == {"resolved": True}

    # The future is now resolved.
    assert req.future.done()
    result = req.future.result()
    assert result.allowed is True
    # Cleanup
    broker.pending.pop(req.approval_id, None)
