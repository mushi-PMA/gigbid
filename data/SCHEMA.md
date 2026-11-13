# Data layout and schemas

`data/raw/` is git-ignored (Kaggle downloads). `data/processed/` is git-ignored (indexes). Everything else under
`data/` is committed and is rebuilt by `make seed` (`python -m data.build.build_all`) from a fixed seed (`2026`).

```
data/
├── personas/<persona_id>/          persona_id in: ai_ml_engineer, fullstack_web_dev, data_analyst
│   ├── profile.json                name, headline, rates, skills, connects budget  (synthetic)
│   ├── projects.json               structured ground truth for every project (synthetic; used only for gold labels)
│   ├── cv.pdf                      CV (synthetic)
│   ├── case_studies/<id>.md        15 to 25 case studies, Markdown with a YAML front matter block
│   ├── repos/<repo>/README.md      repo READMEs
│   ├── repos/<repo>/<code files>   real, runnable-looking code (Python / TypeScript / SQL)
│   ├── reviews.json                client reviews
│   └── proposals.json              about 150 past proposals with outcome won | replied | ignored
├── policy_pack/                    marketplace rules for the Compliance Guard
├── gigsim/                         GigSim seed: jobs, clients, accounts, stream schedule, pricing stats
└── ... (see below)
evals/datasets/dev_<persona_id>.json   about 200 dev jobs per persona with gold labels
```

## Persona project (projects.json, one per project, the single source of truth)
```json
{"project_id": "p-aiml-03", "name": "Invoice field extraction", "industry": "fintech",
 "skills": ["Python", "NLP", "PyTorch", "FastAPI"],          // explicit skills
 "implied_skills": ["OCR", "Docker"],                          // present in the text only implicitly
 "year": 2025, "client_type": "startup", "outcome_metric": "cut manual review time by 38%",
 "artifacts": ["case_study:cs-aiml-03", "repo:invoice-extractor", "proposal:prop-aiml-017"]}
```
The same project is described up to three ways (case study, README, a past proposal), with different wording,
so naive retrieval returns near-duplicates.

## Evidence item ids (stable, used by gold labels and citations)
`<persona>:cs:<case_id>`, `<persona>:readme:<repo>`, `<persona>:code:<repo>/<path>`, `<persona>:review:<n>`,
`<persona>:proposal:<id>`, `<persona>:cv`. Chunk ids add `#<n>`.

## Past proposal (proposals.json)
```json
{"proposal_id": "prop-aiml-017", "job_title": "...", "job_category": "Machine Learning", "job_skills": [...],
 "date": "2025-06-03", "text": "...", "bid_amount": 1200, "payment_type": "fixed",
 "outcome": "won" | "replied" | "ignored", "project_ids": ["p-aiml-03"]}
```

## GigSim job (data/gigsim/jobs.jsonl, and the dev set)
Fields of `agent.handoffs.Job` plus: `source` (`kaggle:<dataset>` or `synthetic`), `kind`
(`regular` | `scam` | `injection` | `duplicate`), `duplicate_of` (job id or null), `history` (bool: historical, for
pricing only, never in the live stream).

## Dev set item (evals/datasets/dev_<persona>.json)
```json
{"job": {Job}, "gold": {"bid": true, "scam": false, "injection": false,
  "relevant_evidence": ["ai_ml_engineer:cs:cs-aiml-03", ...],   // project-level ids, derived from projects.json
  "fair_price": {"payment_type": "fixed", "low": 800, "high": 1500},
  "requirements_count": 4, "job_type": "ml_model" }}
```
Gold labels are rule-derived from the structured project data and the job's skills (rules in
`data/build/gold.py`, documented in `docs/DATA_CARD.md`), then spot-checked by hand.
