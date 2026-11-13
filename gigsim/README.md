# GigSim

GigSim is a small marketplace simulator for development, evaluation and grading. It serves jobs, clients with
histories, Connects, proposals, messages, rate limits and occasional errors. The REST contract is in `API.md`.
The data comes from `data/gigsim/` (see `docs/DATA_CARD.md`).

## Run

```
python -m data.build.download      # once, needs the kagglehub package
python -m data.build.build_all     # builds the seed, personas and evaluation sets (about 2 minutes)
python -m gigsim.server            # http://localhost:8081
```

The database (`GIGSIM_DB`, default `data/gigsim/gigsim.db`) is created from the seed files on the first start.
Delete the file to start again from the seed. Docker: `infra/docker/gigsim.Dockerfile`.

Tokens: each persona has one account in `data/gigsim/accounts.json`. The token is
`sha256("gigsim-seed-2026:<persona_id>")` (a development token, not a secret). The environment variable
`GIGSIM_TOKEN_<PERSONA_ID_IN_UPPER_CASE>` replaces it, for example `GIGSIM_TOKEN_AI_ML_ENGINEER`.

```
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8081/v1/jobs?q=python&limit=5"
```

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `GIGSIM_PORT`, `GIGSIM_HOST` | `8081`, `0.0.0.0` | Where the server listens |
| `GIGSIM_DB` | `data/gigsim/gigsim.db` | SQLite file |
| `GIGSIM_SEED_DIR` | `data/gigsim` | Folder with the seed files |
| `GIGSIM_ERROR_RATE` | `0.02` | Share of calls that fail with `503`, drawn from a seeded RNG (`GIGSIM_SEED`, default 2026) |
| `GIGSIM_RATE_LIMIT_PER_MIN` | `60` | Calls per token per real minute, then `429` with `Retry-After` |
| `GIGSIM_START`, `GIGSIM_SPEED` | `2026-10-27T00:00:00Z`, `1.0` | Simulated clock (speed 0 freezes it) |
| `GIGSIM_ADMIN_TOKEN` | empty | Token for `/admin/*`. Empty means the admin endpoints answer `403` |
| `GIGSIM_LLM` | `off` | `on` asks the model node `gigsim_client` (temperature 0) to judge proposals |

## Behaviour worth knowing

- **Clock.** Jobs appear when their `posted_at` is not after the simulated now. Move time with
  `POST /admin/clock {"now": "2026-11-03T00:00:00Z"}`. `POST /admin/connects {"account_id", "amount"}` adds Connects.
- **Policy.** `v1` before `2026-11-02T00:00:00Z`, `v2` after it. `v2` adds +4 Connects for premium jobs (fixed budget
  of 1000 or more, hourly budget of 50 or more) and the rule `no_external_links` (no `http`, `https` or `www` in cover
  letters and answers). Both versions refuse emails and phone numbers (`off_platform`). A refused submit returns `422`
  with a `violations` list and spends nothing. Not enough Connects returns `402`.
- **Writes.** Send an `Idempotency-Key` header. The same key with the same request returns the first result
  (header `Idempotent-Replay: true`) and never charges twice. The same key with a different request returns `409`.
  `?dry_run=true` returns what would happen and changes nothing. A faulty call with a key can fail after the write
  was done (the answer is lost), so retrying with the same key is the right move.
- **Simulated clients.** Each client has hidden preferences. After a submit, a deterministic score decides the outcome
  (ignored, viewed, declined, replied, interview or hired) and the events arrive later in simulated time, with delays
  that depend on the client's responsiveness. The score rewards must-have skills, personal detail from the job post,
  a price under the client's ceiling and complete screening answers, and punishes generic openings. Clients also write
  first on some jobs, including a few scam and prompt-injection messages. Messages you send get a later answer.
- **Hidden data.** Hidden preferences and labels such as `kind` (scam, injection, duplicate) are never returned.

## Tests

```
python -m pytest gigsim/tests -q
```

The tests use a tiny seed in a temporary folder, a frozen clock and no random faults. Note: `pyproject.toml` must
not start with a byte order mark, or pytest cannot read it (`gigsim/pytest.ini` keeps these tests independent of it).
