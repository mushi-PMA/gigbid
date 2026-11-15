# Failure analysis

Failed dev jobs are collected by `python -m evals.runners.failure_analysis` into `evals/results/failures.json`
(categories: missed evidence, wrong skip, wrong bid, mispriced, unsupported claim, generic opening, compliance miss,
injection, tool error). Each group was then read by hand; the table below records the cause, the fix tried and
whether it worked, with the metric before and after the fix.

## Counts by category (dev set)

<!-- results:failures -->
| Failure category | Dev jobs |
|---|---|
| unsupported claim | 4 |
| wrong bid | 3 |
| wrong skip | 3 |
| missed evidence | 2 |
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
| 12 | dev-aiml-0006 | ai_ml_engineer | missed scam | "Earn $500, data entry, no experience" was skipped for low fit, not flagged as a scam; the scam patterns look for payment and contact tricks, not pay that is too good for the effort | Seven scam rules written from the dev failures (pay too good for no experience, easy money, pay only on final delivery, equipment provided, CV harvesting, act-now pressure, data access setup), and a rule hit is now decisive (commit 23e0cbe) | Yes: scam recall 0.5 to 1.0 on the 30 dev jobs and 0.667 to 1.0 on the 30 holdout jobs (`decisions.json` and `holdout.json`, before: as committed in 361a704); the rules alone catch 42 of 42 dev and 12 of 12 holdout scams and flag 0 of 558 dev and 1 of 138 holdout ordinary jobs (`scam_rules.json`) |

### Proposals (`evals/results/proposals_best.json`, 12 fixed jobs, every job drafted on purpose)

| # | Job ids | Category | Root cause (what the trace shows) | Fix tried | Worked? |
|---|---------|----------|-----------------------------------|-----------|---------|
| 13 | dev-web-0003, dev-web-0005, dev-web-0012, dev-data-0007 | tool error (token budget) | Thin evidence: claim verification deletes the unsupported sentences, the letter falls below 120 words, the Critic sends it back for length, and after two revisions the job passes the 60,000-token budget and goes to a human | (1) The Writer stopped counting evidence ids as words (prompt version 2). (2) The Critic now stops when length is its only complaint after the Writer had one chance to fix it (commit e306eb3) | Partly: replaying the same 12 jobs from the cache with the new rule, it ended two drafts one pass earlier (dev-aiml-0003: 57,204 to 39,869 tokens; dev-data-0005: 50,850 to 36,267), so cost per drafted proposal fell from $0.0102 to $0.0092; unsupported claims (1.00 to 0.63) and the judge score (3.63 to 3.88) changed through those two letters only (`proposals_best.json` against `proposals_best_critic_stop.json`). These 4 jobs still pass the token budget before the stop applies |
| 14 | every proposal job in the first X2, V0 and holdout runs | tool error (evaluation harness) | Calls replayed from the evaluation cache reach the marketplace server far faster than a live run, its per-user rate limiter refused them, and the Pricing node failed (`pricing failed: ToolError`) | The harness turns the limiter off for its offline marketplace copy (the deployed server keeps it), commit 5bb48aa | Yes: after this fix (and fresh provider keys for the timeouts that remained) V0 has no dead letters (`proposals_v0.json`) |
| 15 | every job replayed from the evaluation cache | measurement error | A replayed call takes no time, so a replayed run reported a p95 of 1.0 s per proposal and "met" a budget it had missed (`archive/holdout_replay_console.txt`) | Each node now counts its replayed calls and latency is computed only over fully live jobs, commit eff5d62 | Yes: replays now report latency as not measured; the holdout latency comes from its first, fully live run |

## Patterns

- **One fix removed every dead letter.** Rows 1 to 5 share one cause: reasoning tokens used up the Fit Matcher's
  output budget, and the half-written JSON broke the decision. In the first run this hit 19 of 120 jobs (16%); on
  the 30 shared jobs dead letters fell from 5 to 0 and correct decisions rose from 19 to 22. We do not compare
  latency between these two runs: some calls in each were replayed from the evaluation cache, which takes no time.
- **The matcher is generous with nearby skills** (rows 5 to 7): all three wrong bids have gold coverage of 0.33 or
  less but a fit of 0.60 or more. The opposite error comes from the extractor (rows 8 and 9): named tools become
  extra requirements and drag fit down. Both point to the same next change, separating core skills from named tools
  before matching. It is not built yet, so these rows stay open.
- **Client rules explain the two watched good fits** (rows 10 and 11). We keep the rule: an unverified client with
  no spend is the riskiest place to spend Connects, and the gold label measures skill fit only.
- **Verification and length pull against each other** (row 13). On jobs with little evidence the system escalates
  instead of padding the letter, which is the safe outcome, but it spends the whole token budget first. A cheaper
  stop would end the loop as soon as the Critic's only complaint is length after verification.
- **Scam rules were the cheapest fix with the largest effect** (row 12): seven patterns in the policy pack, no code
  beyond making a hit decisive. The cost is visible on the holdout: an old rule ("free trial") now skips one ordinary
  post that mentions a product's free trial. We did not change the rule because of a holdout job.
