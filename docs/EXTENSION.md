# Signature extension X2: proposal experiments

GigBid can run two proposal strategies as an A/B test in GigSim and decide between them with a significance test on
reply rate, instead of guessing which style works.

## What was built
- **Strategy as configuration.** `writer.strategy` in `agent/config.yaml` (or `WRITER_STRATEGY`) selects the Writer's
  prompt file:
  - **A** (`agent/prompts/writer.md`): open with the client's problem in their words, then the single most relevant
    piece of evidence, then a short plan.
  - **B** (`agent/prompts/writer_strategy_b.md`): open with a two-sentence credentials summary, then a numbered plan,
    then an invitation to a call.
  Both keep every guardrail (evidence citations, claim verification, Critic, Compliance Guard, human approval).
- **Experiment runner** `evals/runners/x2_ab_test.py`: both arms write for the same dev jobs (paired design), every
  proposal is submitted to GigSim's simulated clients (the human approval is simulated only inside the experiment),
  and the result records reply rate per arm, the discordant pairs, an exact McNemar test and a two-proportion
  z-test.
- **Outcome memory link.** The opening type of every submitted proposal is stored with its outcome
  (`agent/memory/promotion_rules.py`), so after an experiment the Writer is told which opening style got replies in
  each job category.

## How it was measured
Paired jobs: the same gold-bid dev jobs for both arms, so client preferences and job difficulty are held constant;
only the strategy differs. With paired binary outcomes the exact McNemar test (binomial test on the jobs where only
one arm got a reply) is the right test; the z-test is reported for comparison.

## Result
<!-- results:x2 -->
| Arm | Reply rate | Only this arm replied |
|---|---|---|
| A: problem first | 85.7% | 1 |
| B: credentials first | 85.7% | 1 |

Paired jobs: 7; exact McNemar p = 1.0; two-proportion z-test p = 1.0.
<!-- /results:x2 -->

Run: `python -m evals.runners.x2_ab_test --per-persona 20`
