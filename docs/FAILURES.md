# Failure analysis

Failed dev jobs are collected by `python -m evals.runners.failure_analysis` into `evals/results/failures.json`
(categories: missed evidence, wrong skip, wrong bid, mispriced, unsupported claim, generic opening, compliance miss,
injection, tool error). Each group was then read by hand; the table below records the cause, the fix tried and
whether it worked, with the metric before and after the fix.

## Counts by category (dev set)

<!-- results:failures -->
_Not measured yet: run `make eval` (needs a model key)._
<!-- /results:failures -->

## Hand analysis (12 failed jobs)

"Before" is the first full dev run (120 jobs, commit 7df0bcb, superseded and archived as
`evals/results/archive/decisions_first_run_7df0bcb.json`);
"after" is `evals/results/decisions.json` (30 jobs, commit dc2aa73). The 30 jobs of the second run are all inside
the first, so the before and after numbers below are on the same 30 jobs. Thresholds: bid at fit 0.55, watch at
0.40, client quality at least 0.20.

| # | Job id | Persona | Category | Root cause (what the trace shows) | Fix tried | Worked? (before, after) |
|---|--------|---------|----------|-----------------------------------|-----------|-------------------------|
| 1 | dev-aiml-0003 | ai_ml_engineer | tool error | Fit Matcher JSON cut off: the model spent its output budget on reasoning, so `fit` was missing and `decide` raised KeyError | Low reasoning effort, fit output budget 2,400 tokens, JSON repair with a larger budget; `decide` now stops with a clear "analysis incomplete" reason | Yes: dead letter, now bid (gold bid) |
| 2 | dev-aiml-0004 | ai_ml_engineer | tool error | Same truncated Fit Matcher JSON | Same as 1 | Yes: dead letter, now bid (gold bid) |
| 3 | dev-data-0007 | data_analyst | tool error | Same truncated Fit Matcher JSON | Same as 1 | Yes: dead letter, now bid (gold bid) |
| 4 | dev-data-0005 | data_analyst | tool error, then wrong skip | Truncated JSON first; after the fix, fit 0.40 (no GraphQL evidence) lands on watch, below the 0.55 bid line | Same as 1 | Partly: dead letter, now watch (gold bid) |
| 5 | dev-web-0010 | fullstack_web_dev | tool error, then wrong bid | Truncated JSON first; after the fix, general web work is counted as cover for WooCommerce, PHP and Photoshop (fit 0.60, gold coverage 0.20) | Same as 1 | Partly: dead letter, now a wrong bid |
| 6 | dev-web-0001 | fullstack_web_dev | wrong bid | Pipedrive and email-marketing automation scored 0.60 because API-integration projects were read as "automation" evidence (gold coverage 0.17) | None yet; planned: weight the post's named tools as core requirements | No |
| 7 | dev-aiml-0002 | ai_ml_engineer | wrong bid | NLP and model evidence covered "AI"; Flask and MongoDB have no evidence, yet fit reached 0.75 (gold coverage 0.33) | None yet; same plan as 6 | No |
| 8 | dev-aiml-0001 | ai_ml_engineer | missed evidence | Requirement extraction turned every named Azure service into a must-have, so the ETL and Spark evidence counted for little (fit 0.10; gold core skills are ETL and Spark) | None yet; planned: cap named services at one requirement per platform | No |
| 9 | dev-web-0003 | fullstack_web_dev | missed evidence | Same over-splitting: "Canopy integration" and "IRS payout formula" became requirements, pushing a plain WordPress form job (gold coverage 1.0) down to fit 0.35 | None yet; same plan as 8 | No |
| 10 | dev-data-0003 | data_analyst | wrong skip (watch) | Fit 0.95, but the client has unverified payment, $0 spent and no hires, so client quality is 0.08 and the job is watched | Kept on purpose: the gold label ignores the client, our policy does not | Not changed (label disagreement) |
| 11 | dev-web-0005 | fullstack_web_dev | wrong skip (watch) | Same client rule (unverified, no spend, no hires); fit 0.40 | Kept on purpose, as in 10 | Not changed (label disagreement) |
| 12 | dev-aiml-0006 | ai_ml_engineer | missed scam | "Earn $500, data entry, no experience" was skipped for low fit, not flagged as a scam; the scam patterns look for payment and contact tricks, not pay that is too good for the effort | None yet; planned: a pay-against-effort rule in the policy pack | No (the skip was still right) |

## Patterns

- **One fix removed every dead letter.** Rows 1 to 5 share one cause: reasoning tokens used up the Fit Matcher's
  output budget, and the half-written JSON broke the decision. In the first run this hit 19 of 120 jobs (16%); on
  the 30 shared jobs dead letters fell from 5 to 0 and correct decisions rose from 19 to 22. Three changes
  made in the same step (low reasoning effort, the portfolio search moved off the event loop, the matcher's searches
  run in parallel) cut p95 latency on the same 30 jobs from 137 s to 75 s; we did not measure them one by one.
- **The matcher is generous with nearby skills** (rows 5 to 7): all three wrong bids have gold coverage of 0.33 or
  less but a fit of 0.60 or more. The opposite error comes from the extractor (rows 8 and 9): named tools become
  extra requirements and drag fit down. Both point to the same next change, separating core skills from named tools
  before matching. It is not built yet, so these rows stay open.
- **Client rules explain the two watched good fits** (rows 10 and 11). We keep the rule: an unverified client with
  no spend is the riskiest place to spend Connects, and the gold label measures skill fit only.
- **Scam recall is the weakest number** (0.5 on the dev set); row 12 shows the patterns miss "easy money" posts.
