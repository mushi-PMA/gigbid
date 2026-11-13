# Runbook

## Start, stop, check

```bash
cp .env.example .env            # fill the secrets; never commit .env
make up                         # docker compose up -d --build (all services)
docker compose -f infra/docker-compose.yml ps
curl -s localhost:8000/api/health | jq     # marketplace and MCP server status (degraded-mode banner)
make down
```

Web on `:8080`, API on `:8000`, Phoenix traces on `:6006`. The `init` service builds the evidence indexes once and
exits; the API and the MCP servers wait for it.

## Schedules

| What | Where | Interval | Why |
|---|---|---|---|
| Scouting (saved searches) | worker cron `scout_all`, every 30 min | each saved search has its own interval (default 4 h) | Enough to see new posts within a working morning; one search call per interval. |
| Live mode scouting floor | `marketplace.upwork.min_poll_minutes` | at least 120 min | Upwork's automation guidance treats aggressive polling as abuse; two hours keeps us far from anything that looks like scraping, and live mode is never graded on speed. |
| Event tracking (pipeline, outcome memory, new client messages) | worker cron `track_all` | 5 min | Events are cheap reads; replies should reach the user quickly. |
| Degraded-mode recovery | worker cron `requeue_degraded` | 5 min | Re-queues jobs stopped by an unavailable marketplace once it answers again. |

All marketplace reads go through the per-user rate limiter (40 per minute, under GigSim's 60).

## Exactly once

- Workers enqueue analysis with a deterministic Arq job id (`analyze:<user>:<job>`), so a restart never analyses a
  job twice; jobs are also keyed by `(user, job_id)` in `jobs_seen`.
- Submission idempotency keys are derived from the graph thread and a hash of the approved payload. A retried or
  replayed submit returns the first result from the marketplace server's idempotency store (and from GigSim's own),
  so Connects are spent once.

Crash test (viva): approve a proposal, then `docker compose kill worker` before it submits, `docker compose start
worker`; the resumed thread submits once. `tests/integration/test_bid_graph.py::test_approval_then_exactly_once_submission_after_crash`
checks the same thing in CI.

## Degraded mode

Kill the marketplace server: `docker compose stop mcp-marketplace`. The UI banner says "Marketplace unavailable: new
work is queued and will resume automatically" (from `/api/health`, `apps/api/routers/analytics.py`). Graph nodes
that need the marketplace stop with `needs_attention: marketplace_unavailable` (`agent/nodes/base.py`), the worker
re-queues them every 5 minutes, and they resume when the server is back (`docker compose start mcp-marketplace`).

## Switching marketplaces

`MARKETPLACE_MODE=upwork_live` in `.env` (or `marketplace.mode` in config), then connect Upwork in Settings. Only the
marketplace server's adapter changes; the graph, prompts and tools are the same.

## Traces

Open Phoenix (`:6006`), project `gigbid`. Every API request carries one trace id through the graph, the MCP servers
and the audit log (`X-Trace-Id` response header). Each LLM span shows tokens and cost.

## Secrets

All secrets come from environment variables. OAuth tokens are encrypted at rest with `TOKEN_ENCRYPTION_KEY`
(Fernet). Rotate `APP_SECRET_KEY` and `MCP_SHARED_SECRET` by changing them in `.env` and restarting; users sign in
again.

## Backups

`docker compose exec postgres pg_dump -U gigbid gigbid > backup.sql` (users, settings, checkpoints, memory, audit).
