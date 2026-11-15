# MCP tools

Agents never call GigSim, Upwork, a database or a file directly; every capability is one of these MCP tools. Each
agent sees only the tools in its allowlist (`mcp.allowlists` in `agent/config.yaml`). Schemas are pinned by the
snapshot test `tests/contract/test_tool_schemas.py`.

Annotations: RO = readOnlyHint, D = destructiveHint, I = idempotentHint, OW = openWorldHint.
Auth: every HTTP endpoint needs a short-lived bearer token (HS256, minted by the API for one user, verified by
`common.security.ServiceTokenVerifier`). Writes also need an approval token minted when the human approved that
exact payload.

## Our servers

| Tool | Server | Read or write | Annotations | Auth | Notes |
|---|---|---|---|---|---|
| `search_evidence(requirement, k, filters)` | portfolio | read | RO, I | bearer (scope portfolio) | Shipped RAG pipeline; returns type, source, date, outcome per item |
| `get_case_study(case_id)` | portfolio | read | RO, I | bearer | Full case study |
| `list_skills()` | portfolio | read | RO, I | bearer | Skills with evidence counts |
| resource `portfolio://case/{case_id}` | portfolio | read | - | bearer | Full case study as Markdown |
| resource `portfolio://proposal/{proposal_id}` | portfolio | read | - | bearer | Past proposal with outcome |
| resource `portfolio://repo/{repo}`, `portfolio://cv` | portfolio | read | - | bearer | README, CV text |
| prompts `answer_screening_question`, `proposal_opening`, `fit_summary` | portfolio | - | - | - | Templates a freelancer would pick in an MCP host |
| `search_jobs(query, skills, category, since, limit)` | marketplace | read | RO, I, OW | bearer (scope marketplace) | Rate-limited per user |
| `get_job(job_id)` | marketplace | read | RO, I, OW | bearer | Job text is untrusted data |
| `get_client_history(client_id)` | marketplace | read | RO, I, OW | bearer | Public history only |
| `get_connects_balance()` | marketplace | read | RO, I, OW | bearer | |
| `list_threads()`, `list_messages(thread_id)` | marketplace | read | RO, I, OW | bearer | Client text is untrusted data |
| `list_events(since)`, `list_proposals()` | marketplace | read | RO, I, OW | bearer | Pipeline and outcome memory |
| `get_policy()`, `get_market_pricing(category, skills)` | marketplace | read | RO, I, OW | bearer | |
| `create_proposal_draft(job_id, cover_letter, bid_amount, payment_type, idempotency_key, screening_answers, dry_run, approval_token)` | marketplace | write | not RO, not D, I, OW | bearer + approval token | `dry_run` returns exactly what would be sent and its cost |
| `submit_proposal(proposal_id, job_id, idempotency_key, approved_payload, dry_run, approval_token)` | marketplace | write | not RO, D, I, OW | bearer + approval token | Spends Connects once per idempotency key |
| `send_message(thread_id, text, idempotency_key, dry_run, approval_token)` | marketplace | write | not RO, D, I, OW | bearer + approval token | |
| `get_free_slots(from_date, days, duration_minutes, tz, max_slots)` | workspace | read | RO, I | bearer (scope workspace) | Working hours, avoids holds |
| `create_interview_hold(start, duration_minutes, title, thread_id, idempotency_key)` | workspace | write | not RO, not D, I | bearer | Tentative hold only |
| `create_email_draft(recipient_label, subject, body, idempotency_key)` | workspace | write | not RO, not D, I | bearer | Draft only, never sent |

Every call to the marketplace server is written to the append-only audit log (user, tool, PII-masked arguments,
result, trace id); the Postgres table rejects UPDATE and DELETE with a trigger.

## MCP Inspector screenshots

Each server run over stdio in the official MCP Inspector (v2.13.0), against a local GigSim:

| Server | Tools and annotations | A real call |
|---|---|---|
| Portfolio | [tools](images/inspector/portfolio-tools.png) (all read-only and idempotent) | [search_evidence result](images/inspector/portfolio-call.png), [portfolio://cv resource](images/inspector/portfolio-resource.png) |
| Marketplace | [submit_proposal](images/inspector/marketplace-submit.png) (destructive, idempotent, open world; needs the approved payload and an approval token) | [search_jobs result](images/inspector/marketplace-call.png) |
| Workspace | [tools](images/inspector/workspace-tools.png) | [call result](images/inspector/workspace-call.png) |

Running them this way found two real problems, both fixed: the first `search_evidence` over stdio never answered on
Windows (`docs/FAILURES.md`, row 16), and the Inspector's schema check flagged the untyped `detail` field in every
marketplace result, which some MCP clients mishandle.

## Third-party servers

| Server | Used for | Tools we call | Trust rationale |
|---|---|---|---|
| Upwork official MCP server (`https://mcp.upwork.com/mcp`, OAuth 2.1) | Live mode behind the same marketplace port | job search, job details, client info, Connects, messages, proposal and message drafts (names mapped in `marketplace.upwork.tool_map`) | Run by the platform itself; every write is a draft the user confirms on Upwork, tokens are scoped to the user and stored encrypted. |
| GitHub official MCP server (`https://api.githubcopilot.com/mcp/`) | Ingesting a freelancer's public repos into the portfolio (`rag/ingest/github.py`) | `get_file_contents` only | Maintained by GitHub; we use a fine-grained token with read-only Contents access and call read tools only. |
