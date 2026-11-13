# GigBid Portfolio MCP server

A read-only MCP server that turns a freelancer's portfolio (CV, case studies, repos, client reviews and past
proposals with outcomes) into evidence you can search and cite. Plug it into any MCP host (desktop chat apps,
code editors such as Cursor) and ask things like "have I built an Airflow pipeline for a retail client?" or pick the prompt "Answer a
screening question from my portfolio".

## Install and run

With [uv](https://docs.astral.sh/uv/) (no clone needed):

```bash
PORTFOLIO_DIR=/path/to/portfolios PORTFOLIO_PERSONA=me MCP_AUTH=off \
  uvx --from git+https://github.com/mushi-PMA/gigbid gigbid-portfolio-mcp --stdio
```

With Docker:

```bash
docker run --rm -i -e MCP_AUTH=off -e PORTFOLIO_PERSONA=me -v /path/to/portfolios:/portfolios \
  -e PORTFOLIO_DIR=/portfolios ghcr.io/mushi-pma/gigbid-portfolio-mcp:latest --stdio
```

In an MCP host's server configuration (the usual `mcpServers` format):

```json
{"mcpServers": {"portfolio": {
  "command": "uvx",
  "args": ["--from", "git+https://github.com/mushi-PMA/gigbid", "gigbid-portfolio-mcp", "--stdio"],
  "env": {"PORTFOLIO_DIR": "/path/to/portfolios", "PORTFOLIO_PERSONA": "me", "MCP_AUTH": "off"}}}}
```

The first run downloads two small open models (embeddings and a reranker, CPU only).

## Portfolio folder

```
portfolios/me/
├── profile.json          {"name": "...", "skills": ["Python", "SQL"]}
├── cv.pdf                optional
├── case_studies/*.md     Markdown; optional front matter: id, title, date, industry, skills
├── repos/<name>/         README.md and code files
├── reviews.json          [{"review_id", "text", "rating", "date"}]
└── proposals.json        [{"proposal_id", "job_title", "text", "outcome": "won|replied|ignored", "date"}]
```

Any part can be missing. Build or refresh the index after changes:
`PORTFOLIO_DIR=... python -m rag.ingest.build_indexes --persona me` (only changed documents are re-embedded).

## Tools, resources, prompts

| Kind | Name | What it does |
|---|---|---|
| tool | `search_evidence(requirement, k, filters)` | Hybrid search (BM25 + dense), reranked, grouped by project; returns type, source, date and outcome for each item. Filters: types, outcome, skills |
| tool | `get_case_study(case_id)` | Full case study |
| tool | `list_skills()` | Skills with how many evidence items mention each |
| resource | `portfolio://case/{id}`, `portfolio://proposal/{id}`, `portfolio://repo/{name}`, `portfolio://cv` | Load full items |
| prompt | `answer_screening_question`, `proposal_opening`, `fit_summary` | Ready-made tasks that search first and cite evidence ids |

All tools are read-only (`readOnlyHint`). Over HTTP (inside GigBid) the server needs a bearer token; with `--stdio`
it runs locally for one person.
