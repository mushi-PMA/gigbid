# GigSim REST API (v1)

GigSim is a marketplace simulator used for development, evaluation and grading. It is seeded from public Upwork
datasets (jobs, budgets, Connects costs, client signals) plus clearly labelled synthetic data (personas, clients'
hidden preferences, scams, injected posts, conversations). Every response is JSON. Base URL `GIGSIM_BASE_URL`
(default `http://localhost:8081`).

## Auth, limits and errors
- Every call needs `Authorization: Bearer <token>`. Tokens map to a freelancer account (`data/gigsim/accounts.json`).
- Rate limit: `GIGSIM_RATE_LIMIT_PER_MIN` (default 60) per token. Over the limit: `429` with a `Retry-After`
  header (seconds).
- Fault injection: `GIGSIM_ERROR_RATE` (default 0.02) of calls return `503 {"error": "temporarily unavailable"}`,
  drawn from a seeded RNG so runs are repeatable. `GIGSIM_ERROR_RATE=0` disables it (tests).
- Write calls take an `Idempotency-Key` header. Repeating a key returns the first result and never charges twice.
- Simulated clock: `GIGSIM_START` (ISO time, default `2026-10-27T00:00:00Z`) and `GIGSIM_SPEED` (default 1.0).
  `POST /admin/clock {"now": "..."}` moves the clock (needs `GIGSIM_ADMIN_TOKEN`). Jobs become visible when their
  `posted_at` is not after the simulated now.

## Read endpoints
| Method and path | Returns |
|---|---|
| `GET /health` | `{"status": "ok", "now": ..., "policy_version": ...}` (no auth) |
| `GET /v1/jobs?q=&skills=a,b&category=&since=&limit=50&offset=0` | `{"jobs": [Job], "total": n}`; newest first; `q` matches title and description (case-insensitive, all words) |
| `GET /v1/jobs/{job_id}` | `Job` |
| `GET /v1/clients/{client_id}` | `ClientHistory` (public history only; hidden preferences are never exposed) |
| `GET /v1/connects` | `{"balance": int, "weekly_budget_left": int|null}` |
| `GET /v1/proposals` | `{"proposals": [Proposal]}` for this account |
| `GET /v1/proposals/{proposal_id}` | `Proposal` |
| `GET /v1/threads` | `{"threads": [{"thread_id", "job_id", "client_id", "last_message_at", "unread": int}]}` |
| `GET /v1/threads/{thread_id}/messages` | `{"messages": [Message]}` |
| `GET /v1/events?since=<iso>` | `{"events": [{"event_id", "type", "proposal_id", "thread_id", "at", "data"}]}`; types: `proposal_viewed`, `client_replied`, `interview_requested`, `hired`, `declined` |
| `GET /v1/policy` | `{"version": str, "effective_from": iso, "rules": [{"id", "text"}], "connects": {...}}` |
| `GET /v1/market/pricing?category=&skills=a,b` | `{"category", "n", "fixed": {"p25","p50","p75"}, "hourly": {"p25","p50","p75"}}` from the historical jobs |

## Write endpoints (all accept `?dry_run=true`, which returns exactly what would happen and its cost, changes nothing)
| Method and path | Body | Effect |
|---|---|---|
| `POST /v1/proposals` | `{"job_id", "cover_letter", "screening_answers": [{"question","answer"}], "bid_amount", "payment_type"}` | Creates a proposal in `draft` status; no Connects spent |
| `POST /v1/proposals/{proposal_id}/submit` | `{}` | Spends the job's Connects (per current policy) and submits; the simulated client then decides (see below). `402` if not enough Connects; `422` with `{"violations": [...]}` if the proposal breaks a platform rule |
| `POST /v1/threads/{thread_id}/messages` | `{"text"}` | Sends a freelancer message; the client may answer later |

## Simulated clients
Each client has hidden preferences (`must_have_skills`, `budget_ceiling`, `dislikes_generic_openings`,
`wants_screening_answers`, `responsiveness`). After a submit, GigSim scores the proposal against them and asks an
LLM judge (profile from `GIGSIM_LLM_*`, temperature 0, cached by proposal hash) whether to view, reply, interview or
hire; without an LLM it uses the deterministic score only. Outcomes arrive as events over simulated time.

## Platform policy versions (change request)
`v1` applies before `2026-11-02T00:00:00Z`; `v2` from then on. The policy endpoint always returns the version in
force at the simulated now, and submit enforces it.
