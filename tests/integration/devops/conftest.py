"""Env setup for live DevOps integration tests.

Mirrors tests/unit/devops/conftest.py so the live tests can import
`config.settings` without the Pydantic validators raising. The live tests
themselves still require the real DEVOPS env vars (GITHUB_TOKEN,
DIGITALOCEAN_TOKEN, ANTHROPIC_API_KEY) — those are not stubbed.
"""
from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "x" * 64)
os.environ.setdefault("ENCRYPTION_KEY", "y" * 64)
os.environ.setdefault("HCX_API_URL", "http://hcx.test/api")
os.environ.setdefault("HCX_GATEWAY_URL", "http://hcx.test/gw")
os.environ.setdefault("HCX_USERNAME", "test_user")
os.environ.setdefault("HCX_PASSWORD", "test_pw")
os.environ.setdefault("DB_PASSWORD", "test_db_pw")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
