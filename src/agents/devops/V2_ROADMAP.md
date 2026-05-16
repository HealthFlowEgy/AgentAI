# DevOps Agent v2 — Roadmap

Captured here because GitHub Issues are disabled on this repo. Each
section below is intended to become a single issue once Issues are
turned on; the body of each section is already issue-ready.

---

## 1. Preview-env provisioning workflow (`devenv_provision_preview` / `devenv_teardown_preview`)

**Context.** v1 ships `devenv_describe_pr` and `devenv_status` as
read-only tools; full preview-env provisioning is deferred. The agent
currently has to chain individual `gh_*` + `do_*` mutating tools, each
approved separately.

**Goal.** A single `devenv_provision_preview(pr_url, spec_overrides?)`
tool that:

1. Fetches PR head ref + changed files via `gh_get_pr` / GraphQL.
2. Renders a preview-env spec from a per-repo template (YAML in the repo
   or a fallback in `src/agents/devops/devenv/templates/`).
3. Creates or updates the corresponding DigitalOcean App Platform app
   with the PR head ref.
4. Seeds preview-only secrets (read from a designated GitHub Actions
   secret store or a per-team vault).
5. Optionally configures a DNS record (`preview-<pr#>.<domain>`).
6. Posts the preview URL back to the PR via `gh_comment_issue`.
7. Records a TTL so `devenv_teardown_preview` can be invoked
   automatically (cron job or scheduled hook).

`devenv_teardown_preview(pr_url)` reverses (4)–(6) and removes the DNS
entry.

**Constraints.**
- One mutating call per approval — composed mutations still go through
  `can_use_tool` per child step.
- Spec DSL stays small (resource sizes, env vars, build/run commands,
  optional DB attachment). No full Terraform replacement.
- The tool itself must declare `read_only=False` and pass the build-time
  registry test.

**Touchpoints.**
- `src/agents/devops/tools/devenv_tools.py` — replace v1 stubs.
- `src/agents/devops/devenv/` — new subpackage for templates + renderer.
- `tests/unit/devops/test_devenv_tools.py` — respx-mocked end-to-end
  test of one provision call.

---

## 2. Kubernetes mutating operations (apply / delete / scale)

**Context.** v1 ships read-only K8s tools
(`do_list_kubernetes_clusters`, `do_get_kubeconfig` redacted, and an
allow-listed `do_kubectl_get`). Mutations are intentionally deferred.

**Goal.** Three new mutating tools, each with `read_only=False`:
- `k8s_apply(cluster_id, manifest)` — applies a YAML manifest.
  Validates against a per-cluster allow-list of namespaces.
- `k8s_delete(cluster_id, resource, namespace)` — deletes a single
  resource by kind + name.
- `k8s_scale(cluster_id, namespace, deployment, replicas)` — scales a
  Deployment.

**Implementation notes.**
- Use the `kubernetes_asyncio` client rather than shelling to `kubectl`,
  so we don't ship a kubectl binary in the API container.
- Kubeconfig is fetched via `do_get_kubeconfig` and held in an
  in-memory cache per session; never logged or returned to the agent.
- Manifests passed in must round-trip through `yaml.safe_load` before
  transport.
- For namespaces outside the allow-list, the tool returns a
  `PermissionResultDeny` *before* the approval prompt — defense in depth.

**Touchpoints.**
- `src/agents/devops/tools/k8s_tools.py` (new module).
- `requirements.txt` — add `kubernetes_asyncio`.
- `tests/unit/devops/test_k8s_tools.py`.

---

## 3. Redis-backed approval coordinator (horizontal scaling)

**Context.** `FutureBackedBroker` in `src/agents/devops/permissions.py`
keeps pending approvals in a process-local `dict[approval_id,
asyncio.Future]`. The Slack and FastAPI handlers resolve from the same
in-memory map. That works for a single uvicorn worker; it breaks the
moment we add a second worker (Slack callback hits worker B while the
agent is waiting on worker A's Future).

**Goal.** Replace the in-memory map with a Redis-backed coordinator.

**Design sketch.**
- Each `new_request` writes an entry to a Redis hash
  `devops:approvals:<id>` with TTL = `DEVOPS_APPROVAL_TIMEOUT_S`.
- The worker that owns the in-flight agent run subscribes to a per-id
  pub/sub channel `devops:approvals:<id>:result`.
- Any worker handling `/approve` (HTTP) or Slack interactive publishes
  the decision to that channel.
- `await asyncio.wait_for(subscriber.get_message(...), timeout=...)`
  replaces the current `await future` line — single-line surgery
  inside `FutureBackedBroker.request`.

**Constraints.**
- Don't introduce a new abstraction; keep the `ApprovalBroker` interface
  unchanged so the CLI/AutoAllow/AutoDeny brokers keep working.
- Reuse `settings.REDIS_HOST` / `redis_url` — no new connection strings.
- A Redis outage falls back to per-process state and logs a structured
  warning (not silent).

**Touchpoints.**
- `src/agents/devops/permissions.py`.
- `tests/unit/devops/test_permissions.py` — add a fakeredis-backed test
  proving two-process resolution works.

---

## 4. GitHub App authentication (replace PAT)

**Context.** v1 authenticates to GitHub with a single PAT held in
`GITHUB_TOKEN`. PATs (a) inherit the human user's full permissions, (b)
expire and require rotation, and (c) are a poor fit for multi-repo /
multi-org use. The dependency is already in place: `requirements.txt`
pins `githubkit[auth-app]`.

**Goal.** Allow the agent to authenticate as a GitHub App installation.

**Design.**
- New settings: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` (PEM, base64
  in env), `GITHUB_APP_INSTALLATION_ID` (optional; otherwise resolve
  per `owner` at call time).
- `tools/_http.py` grows a `github_app_client(owner_or_installation_id)`
  that mints short-lived installation tokens via
  `githubkit.GitHub(AppInstallationAuthStrategy(...))`.
- Existing tools change from `github_client(_token())` to
  `github_client(owner=args['owner'])`. Token is the PAT only when
  `GITHUB_APP_ID` is unset.
- Tokens cached in-memory with TTL = `min(expires_at - 60s, 30min)`.

**Constraints.**
- Backwards compatible: if `GITHUB_APP_ID` is unset, fall back to the v1
  PAT path.
- Never log the installation token (`audit.redact()` already covers most
  keys, but verify).
- Rate-limit handling: GitHub Apps share a separate rate-limit bucket —
  surface 403 headers as actionable error messages.

**Touchpoints.**
- `config/settings.py`, `.env.example`, `.env.production.example`.
- `src/agents/devops/tools/_http.py`.
- `src/agents/devops/tools/github_tools.py` (mechanical signature change).
- `tests/unit/devops/test_github_tools.py`.

---

## 5. Multi-tenant approval routing (per-repo / per-resource approver groups)

**Context.** v1 has a single global `DEVOPS_SLACK_APPROVERS` list. Any
approver can approve any tool call. For teams that share one bot across
multiple repos, this is too coarse.

**Goal.** Route approvals to the right humans based on which resource
the tool is acting on.

**Design.**
- New settings file `config/devops-approvers.yaml` (or stored in
  Postgres) with shape:

  ```yaml
  github:
    "HealthFlowEgy/AgentAI":
      approvers: ["U_alice", "U_bob"]
      slack_channel: "C_dev"
    default:
      approvers: ["U_alice"]
      slack_channel: "C_ops"
  digitalocean:
    droplets:
      tag:"prod":
        approvers: ["U_carol"]
        slack_channel: "C_prod-changes"
      default:
        approvers: ["U_alice"]
        slack_channel: "C_ops"
  ```

- `ApprovalBroker.request` inspects `req.input_data` to pick the right
  approver group, then posts the Slack card to the matching channel.
- The HTTP `/approve` endpoint accepts an `Authorization` header from
  any approver in the matched group (not just `role=admin`).

**Touchpoints.**
- `src/agents/devops/approvers.py` (new) — config loader + matcher.
- `src/agents/devops/interfaces/slack.py` — channel selection.
- `src/agents/devops/interfaces/api.py` — `/approve` access check.
- `tests/unit/devops/test_approvers.py`.

---

## 6. Per-session cost guardrails (budget caps)

**Context.** v1 has `DEVOPS_MAX_TURNS=20`. That caps turn count but not
spend — a single turn can burn a lot of Claude tokens, and we have no
visibility into per-session cost.

**Goal.** Stop a runaway session before it exceeds a configured USD
budget.

**Design.**
- New setting `DEVOPS_MAX_BUDGET_USD: float = 1.00` per session.
- A `hook` callback registered with `ClaudeAgentOptions(hooks=...)`
  intercepts every `Message` and increments a running USD total from
  the SDK's token usage metadata (`prompt_tokens` * input price +
  `completion_tokens` * output price). Prices are kept in a model-id
  → price dict in `src/agents/devops/pricing.py`.
- When the total exceeds the cap, the next `can_use_tool` call returns
  `PermissionResultDeny("budget exceeded")` regardless of tool type.
- The SSE stream emits an `event: budget` frame once per 10c of spend
  so clients can show a progress meter.

**Touchpoints.**
- `src/agents/devops/agent.py` — wire the hook.
- `src/agents/devops/pricing.py` — new.
- `src/agents/devops/permissions.py` — budget gate.
- `tests/unit/devops/test_budget.py`.

---

## 7. Additional capability surfaces (security scan, perf monitoring, incident response)

**Context.** The reference DevOps-agent taxonomy
(Yash-Kavaiya/Devops-AI-Agents) identifies 8 common surfaces; v1 covers
three (CI/CD via Actions, Cloud Infra via DO, dev-env provisioning).
The remaining five are deferred. v2 picks up the three highest-leverage
ones for HealthFlow.

**Goal.** Three new tool clusters, each as an SDK MCP server alongside
`github` / `do` / `devenv`:

- **`secscan` server** — read-only by design.
  - `secscan_run_codeql(owner, repo, ref)` — kicks off a workflow_dispatch
    on the standard CodeQL workflow (reuses `gh_dispatch_workflow`).
  - `secscan_list_alerts(owner, repo)` — reads
    `/repos/{owner}/{repo}/code-scanning/alerts`.
  - `secscan_get_secret_alerts(owner, repo)` — reads
    `/repos/{owner}/{repo}/secret-scanning/alerts`.
- **`perfmon` server** — read-only.
  - `perfmon_droplet_metrics(droplet_id, metric, since)` — DigitalOcean
    Monitoring API.
  - `perfmon_app_metrics(app_id, since)` — App Platform metrics.
- **`incident` server** — mostly read, one mutating tool.
  - `incident_list_open_alerts()` — pulls from DO Monitoring + GitHub
    issues tagged `incident`.
  - `incident_create(title, severity, owner_team)` — mutating; opens a
    GitHub issue with the right labels + posts to the team's Slack
    channel.
  - `incident_resolve(issue_number)` — mutating; closes the issue and
    posts the resolution comment.

**Constraints.**
- Each new tool follows the `read_only` annotation contract — the
  build-time registry test will fail the suite if a tool forgets it.
- Reuse `github_client` / `do_client` from `tools/_http.py`. No new HTTP
  client.

**Touchpoints.**
- `src/agents/devops/tools/secscan_tools.py`, `perfmon_tools.py`,
  `incident_tools.py` (new modules).
- `src/agents/devops/tools/__init__.py` — extend `_REGISTRY` to include
  `secscan`, `perfmon`, `incident`.
- `src/agents/devops/prompts.py` — mention the new MCP server prefixes
  in the capabilities section.
- Unit tests for each module with respx-mocked APIs.

---

## How to enable GitHub Issues for this repo

Go to **Settings → General → Features → Issues** and tick the box.
Once enabled, each H2 above (`## 1.`, `## 2.`, …) is paste-ready as a
single issue.
