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

## Deploy (Azure VM)

```bash
bash infra/deploy/azure/provision.sh                                    # once: VM, ports 80/443, public name
SITE_HOST=<name>.<region>.cloudapp.azure.com bash infra/deploy/azure/deploy.sh gigbid@<name>.<region>.cloudapp.azure.com
```

`deploy.sh` checks out the public repository on the VM, copies the local `.env.production` (never committed) to
`.env`, and starts the stack with Caddy in front (automatic HTTPS). On the VM, every compose command needs
`--env-file .env`, because compose reads the env file next to the first compose file (`infra/`) by default:

```bash
dc() { docker compose -f infra/docker-compose.yml -f infra/deploy/docker-compose.prod.yml --env-file .env "$@"; }
dc ps; dc logs --tail 50 worker
```

## Model providers and quotas

The `open` profile uses a pool of free hosted endpoints (`models.endpoints` in `agent/config.yaml`). Each key and
each model is its own lane; a lane that returns a rate limit rests until its `retry-after`. Free tiers have daily
limits as well (Groq: 200,000 tokens per model per key per day), so:
- the live site and the evaluations use **different keys**, so an evaluation run can never use up the site's quota;
- when the small model's lanes all rest for long (a daily limit), frequent nodes fall back to the large model at once
  (`fallback`, `fallback_after_seconds`); every call records the model that answered;
- the scout analyses at most `auto_analyze_per_scout` (default 5) new jobs automatically; the rest wait for a click,
  so the quota serves the jobs people actually open.

## Simulated marketplace clock

GigSim runs a simulated clock (`GIGSIM_START`, default `2026-11-08T00:00:00Z` on the server, speed 1). Jobs appear
when their posting time is not after the simulated now, so the inbox fills like a live feed. Restarting GigSim starts
the clock again from `GIGSIM_START`. Move it by hand with `POST /admin/clock` (needs `GIGSIM_ADMIN_TOKEN`).

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

Open Phoenix (`:6006` locally, `/phoenix/` on the server), project `gigbid`. Every API request carries one trace id
through the graph, the MCP servers and the audit log (`X-Trace-Id` response header). Each LLM span shows tokens and
cost. A pause for human approval shows as an event on the node span, not as an error.

On the server Phoenix has login on (its own secrets in `.env`); the services send traces with the admin secret as a
bearer key, and graders get a read-only viewer account. Phoenix keeps its tables in its own Postgres schema
(`phoenix`), because it has a `users` table of its own.

## Secrets

All secrets come from environment variables. OAuth tokens are encrypted at rest with `TOKEN_ENCRYPTION_KEY`
(Fernet). Rotate `APP_SECRET_KEY` and `MCP_SHARED_SECRET` by changing them in `.env` and restarting; users sign in
again.

## Backups

`docker compose exec postgres pg_dump -U gigbid gigbid > backup.sql` (users, settings, checkpoints, memory, audit).
