"""Test setup for DevOps agent tests.

Pre-populates the env vars that ``config.settings.Settings`` requires so
test modules can ``from config.settings import settings`` without the
Pydantic validators raising. Provides a ``fake_sdk`` fixture that injects
minimal stubs for the Claude Agent SDK so tests that exercise the
permission gate don't need the real SDK installed.
"""
from __future__ import annotations

import os
import sys
import types

import pytest

# --- Required env for config.settings ---------------------------------------

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "x" * 64)
os.environ.setdefault("ENCRYPTION_KEY", "y" * 64)
os.environ.setdefault("HCX_API_URL", "http://hcx.test/api")
os.environ.setdefault("HCX_GATEWAY_URL", "http://hcx.test/gw")
os.environ.setdefault("HCX_USERNAME", "test_user")
os.environ.setdefault("HCX_PASSWORD", "test_pw")
os.environ.setdefault("DB_PASSWORD", "test_db_pw")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("GITHUB_TOKEN", "gh-test-token")
os.environ.setdefault("DIGITALOCEAN_TOKEN", "do-test-token")


# --- Minimal Claude Agent SDK stub -----------------------------------------

def _install_sdk_stub() -> None:
    if "claude_agent_sdk" in sys.modules:
        return

    mod = types.ModuleType("claude_agent_sdk")

    class _Result:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class PermissionResultAllow(_Result):
        def __init__(self, updated_input=None):
            super().__init__(updated_input=updated_input or {})

    class PermissionResultDeny(_Result):
        def __init__(self, message: str = "", interrupt: bool = False):
            super().__init__(message=message, interrupt=interrupt)

    class ToolAnnotations(_Result):
        def __init__(self, readOnlyHint: bool | None = None, **kw):
            super().__init__(readOnlyHint=readOnlyHint, **kw)

    def tool(name, description, input_schema, annotations=None):
        def deco(fn):
            fn._mcp_meta = {
                "name": name,
                "description": description,
                "input_schema": input_schema,
                "annotations": annotations,
            }
            return fn
        return deco

    def create_sdk_mcp_server(name, version, tools):
        return {"name": name, "version": version, "tools": tools}

    class ClaudeAgentOptions(_Result):
        pass

    class ClaudeSDKClient:
        def __init__(self, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def query(self, prompt, session_id="default"):
            self.last_prompt = (prompt, session_id)

        async def receive_response(self):
            return
            yield  # pragma: no cover

    mod.PermissionResultAllow = PermissionResultAllow
    mod.PermissionResultDeny = PermissionResultDeny
    mod.ToolAnnotations = ToolAnnotations
    mod.tool = tool
    mod.create_sdk_mcp_server = create_sdk_mcp_server
    mod.ClaudeAgentOptions = ClaudeAgentOptions
    mod.ClaudeSDKClient = ClaudeSDKClient

    sys.modules["claude_agent_sdk"] = mod


_install_sdk_stub()


@pytest.fixture
def sdk_stub():
    """Re-installable handle in case a test wants to swap behavior."""
    return sys.modules["claude_agent_sdk"]
