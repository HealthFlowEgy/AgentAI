"""CLI interface for the DevOps agent.

Usage:
    devops-agent                              # interactive REPL
    devops-agent --prompt "list my droplets"  # one-shot
    devops-agent --read-only --prompt "..."   # diagnostic mode
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile

import click
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.prompt import Prompt

from src.agents.devops.audit import redact
from src.agents.devops.permissions import (
    ApprovalBroker,
    ApprovalRequest,
    ApprovalResult,
)

_console = Console()


class CliBroker(ApprovalBroker):
    """Synchronous-style approval prompt rendered via rich."""

    interface = "cli"

    async def request(self, req: ApprovalRequest) -> ApprovalResult:
        # Rich prompts are sync; run in default executor so we don't block
        # the event loop the SDK is using.
        return await asyncio.get_running_loop().run_in_executor(
            None, self._prompt_sync, req
        )

    def _prompt_sync(self, req: ApprovalRequest) -> ApprovalResult:
        _console.print(
            Panel(
                JSON(json.dumps(redact(req.input_data))),
                title=f"Approval required: [bold]{req.tool_name}[/bold]",
                border_style="yellow",
            )
        )
        choice = Prompt.ask(
            "Approve?",
            choices=["y", "n", "e"],
            default="n",
        )
        if choice == "y":
            return ApprovalResult(allowed=True, decided_by=os.environ.get("USER", "cli"))
        if choice == "e":
            edited = self._edit_input(req.input_data)
            return ApprovalResult(
                allowed=True,
                updated_input=edited,
                decided_by=os.environ.get("USER", "cli"),
            )
        return ApprovalResult(
            allowed=False,
            reason="Rejected by operator at CLI prompt.",
            decided_by=os.environ.get("USER", "cli"),
        )

    def _edit_input(self, input_data: dict) -> dict:
        editor = os.environ.get("EDITOR", "vi")
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".json", delete=False
        ) as fh:
            json.dump(input_data, fh, indent=2)
            path = fh.name
        try:
            os.system(f"{editor} {path}")  # noqa: S605 — operator-controlled
            with open(path) as fh2:
                return json.load(fh2)
        finally:
            os.unlink(path)


async def _run(prompt: str | None, read_only: bool, session: str) -> None:
    from src.agents.devops.agent import open_session

    async with open_session(broker=CliBroker(), read_only_mode=read_only) as client:
        if prompt:
            await client.query(prompt, session_id=session)
            await _stream(client)
            return
        _console.print(
            Panel(
                "Interactive DevOps agent. Ctrl+D to exit. "
                f"Mode: [{'red' if read_only else 'green'}]"
                f"{'READ-ONLY' if read_only else 'READ-WRITE'}[/]",
                border_style="cyan",
            )
        )
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, lambda: input("devops> "))
            except EOFError:
                _console.print("[dim]bye[/dim]")
                return
            if not line.strip():
                continue
            await client.query(line, session_id=session)
            await _stream(client)


async def _stream(client) -> None:
    async for msg in client.receive_response():
        _render_message(msg)


def _render_message(msg) -> None:
    text = getattr(msg, "text", None)
    if text:
        _console.print(text, end="")
        return
    # Fallback: print the type name for non-text messages so the operator
    # can see tool calls/results scrolling by.
    _console.print(f"[dim][{type(msg).__name__}][/dim]")


@click.command(name="devops-agent")
@click.option("--prompt", "prompt", default=None, help="One-shot prompt; omit for REPL.")
@click.option("--read-only", is_flag=True, help="Disable all mutating tools.")
@click.option("--session", default="cli", help="Session id to scope conversation.")
def main(prompt: str | None, read_only: bool, session: str) -> None:
    """Run the DevOps agent from the command line."""
    asyncio.run(_run(prompt, read_only, session))


if __name__ == "__main__":
    main()
