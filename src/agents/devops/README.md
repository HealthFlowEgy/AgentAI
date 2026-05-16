# DevOps Engineering Agent

A Claude-Agent-SDK-based agent that manages **GitHub** and **DigitalOcean**
on the team's behalf. Every mutating tool call is gated by a
human-in-the-loop approval; read-only tools auto-approve.

## Capabilities

| Surface | Read-only | Mutating |
|---|---|---|
| GitHub (`mcp__github__*`) | repos, branches, PRs, issues, Actions runs/logs | branch/PR/issue create/merge/close/comment, workflow dispatch + rerun, set Actions secret |
| DigitalOcean (`mcp__do__*`) | droplets, apps, deployments, app logs, managed DBs, K8s clusters, kubeconfig (redacted) | create/destroy droplet, droplet actions, App Platform deployments + spec update, DB resize |
| Dev-env workflows (`mcp__devenv__*`) | `devenv_describe_pr`, `devenv_status` | (deferred — v1 composes underlying mutating tools, each gated individually) |

34 tools total in v1: 19 read-only, 15 mutating.

## Configuration

Set in `.env.<environment>` (see repo root `.env.example`):

```
ANTHROPIC_API_KEY=sk-ant-...          # required
GITHUB_TOKEN=ghp_...                  # required; scopes: repo, workflow
DIGITALOCEAN_TOKEN=dop_v1_...         # required; read+write
DEVOPS_READ_ONLY_MODE=false           # env-level kill switch
DEVOPS_AGENT_MODEL=claude-opus-4-7    # any Claude model id
DEVOPS_MAX_TURNS=20
DEVOPS_APPROVAL_TIMEOUT_S=300

# Optional Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_APPROVAL_CHANNEL=C0123456789
DEVOPS_SLACK_APPROVERS=["U0123","U0456"]
```

The settings are **optional** at app startup so the rest of the FastAPI
app keeps running without them. The agent validates them at session
construction (`build_agent_options`) and raises a clear error if any
required one is missing.

## Interfaces

### CLI

```bash
# Interactive REPL
python -m src.agents.devops

# One-shot
python -m src.agents.devops --prompt "list my droplets"

# Read-only diagnostic mode
python -m src.agents.devops --read-only --prompt "what's failing in CI on owner/repo?"
```

Approvals are rendered as a panel showing tool name + redacted JSON input;
press `y` to approve, `n` to deny, `e` to open `$EDITOR` on the JSON and
return an `updated_input`.

### FastAPI

The router auto-mounts under `/api/devops` from `src/api/main.py`.

| Method | Path | Body |
|---|---|---|
| `GET` | `/api/devops/health` | — |
| `POST` | `/api/devops/chat` | `{message, session_id?, read_only?}` → SSE stream |
| `POST` | `/api/devops/approve` | `{approval_id, decision: "allow"\|"deny", updated_input?, reason?}` |
| `GET` | `/api/devops/approvals` | list in-flight approvals (admin-only) |
| `POST` | `/api/devops/slack/events` | Slack URL verification + events |
| `POST` | `/api/devops/slack/interactive` | Slack button-click approvals |

SSE frames emitted by `/chat`:

```
event: token              data: {"text": "..."}
event: tool_use           data: {"name": "...", "input": {...redacted...}}
event: approval_required  data: {"approval_id": "...", "tool": "...", "input": {...}}
event: tool_result        data: {"name": "...", "ok": true}
event: done               data: {}
```

The client resumes the agent by `POST /api/devops/approve` with the
matching `approval_id`. The agent is suspended on an `asyncio.Future`
until the approval (or timeout) arrives.

### Slack

1. Create a Slack app, install it to your workspace, and grant `chat:write`,
   `app_mentions:read`, `commands`, and the necessary scopes for interactive
   components.
2. Point **Event Subscriptions** → Request URL at
   `https://<your-host>/api/devops/slack/events`.
3. Point **Interactivity & Shortcuts** → Request URL at
   `https://<your-host>/api/devops/slack/interactive`.
4. Set `SLACK_SIGNING_SECRET` and put the approving user IDs in
   `DEVOPS_SLACK_APPROVERS` (Slack `Uxxx` IDs, NOT usernames).

Approval cards are Block Kit messages with **Approve** / **Deny** buttons.
Only users in `DEVOPS_SLACK_APPROVERS` can click; others get 403.

## Safety model

The single source of truth for "is this tool safe to auto-approve?" is
the `readOnlyHint` annotation declared at the tool definition site
(`src/agents/devops/tools/*.py`).

```
@devops_tool(
    server="github",
    name="gh_list_repos",
    description="...",
    input_schema={...},
    read_only=True,        # <-- this drives the gate
)
async def gh_list_repos(args): ...
```

`make_can_use_tool` (in `permissions.py`) consults the registry on every
call:

1. Tool is read-only → `PermissionResultAllow` (no human in the loop).
2. `DEVOPS_READ_ONLY_MODE` is on → `PermissionResultDeny` with a clear
   reason. The system prompt instructs the agent to describe what it
   *would* do instead of retrying.
3. Otherwise → delegate to the active `ApprovalBroker`.
   - **CliBroker** prompts with rich panel.
   - **FutureBackedBroker** (used by FastAPI + Slack) suspends on an
     `asyncio.Future` keyed by `approval_id`. The HTTP `/approve`
     endpoint and the Slack interactive handler both resolve the same
     future map.

Every decision is written through `audit.py` as one structlog JSON
line with redacted inputs.

## Adding a tool

1. Edit one of `src/agents/devops/tools/{github,digitalocean,devenv}_tools.py`.
2. Decorate with `@devops_tool(server=..., name=..., description=...,
   input_schema=..., read_only=...)`. The `read_only` flag is **required** —
   the build-time test (`test_every_registered_tool_has_explicit_read_only_classification`)
   fails the suite if a tool forgets it.
3. The handler is `async def fn(args: dict) -> dict` and returns the
   SDK's content-block shape; use `json_block()` or `text_block()`
   from `tools/_http.py`.

## Testing

```bash
# Unit (no network, ~1s)
python -m pytest tests/unit/devops/ \
  --rootdir=tests/unit/devops --confcutdir=tests/unit/devops -o "addopts="

# Live integration (skipped unless RUN_DEVOPS_LIVE=1)
RUN_DEVOPS_LIVE=1 \
  GITHUB_TOKEN=... DIGITALOCEAN_TOKEN=... \
  DEVOPS_LIVE_GH_OWNER=<org> DEVOPS_LIVE_GH_REPO=<repo> \
  python -m pytest tests/integration/devops/test_smoke.py \
    --rootdir=tests/integration/devops --confcutdir=tests/integration/devops -o "addopts="
```

The unit suite covers: permission gate (auto-allow, read-only deny, broker
allow/deny/timeout, registry sanity), respx-mocked GitHub + DigitalOcean
smoke tests, FastAPI approval flow, and Slack signature/approver
validation. The live suite is **read-only by design** — it never mutates
state.

## Roadmap (v2)

Tracked as GitHub issues. Highlights:

- Full preview-env workflow (`devenv_provision_preview` / `..._teardown_preview`)
  with a small spec DSL, secret seeding, DNS, and teardown TTL.
- Kubernetes mutating ops (`kubectl apply / delete / scale`).
- Replace in-process approval `Future` map with Redis pub/sub so the API
  can scale horizontally.
- GitHub App authentication via `githubkit[auth-app]` instead of PAT.
- Multi-tenant approval routing (per-repo approver groups).
- Cost guardrails (per-session budget caps).
- Additional surfaces: security scanning, perf monitoring, incident
  response (from the wider DevOps-agent taxonomy).
