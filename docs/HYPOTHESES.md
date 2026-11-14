# Pre-registered hypotheses

Written and committed before any model-based evaluation was run (see this file's commit time against the results
files in `evals/results/`). Each hypothesis names its test set, metric and the result that would refute it.

## R&D question A: tool granularity
**H-A.** On the 40 tool tasks, GigBid's real tool set with rewritten descriptions (10 tools) has higher
tool-selection accuracy and higher argument accuracy than both the fine set (18 narrow tools) and the coarse set
(3 tools with an `action` enum). The coarse set uses the fewest tokens per task but has the lowest argument accuracy,
because its free `params` object has no schema.
*Refuted if* the fine or coarse set matches or beats the best set on both accuracies.

## R&D question B: retrieval
**H-B1.** Requirement decomposition plus hybrid retrieval and reranking (V1+V2+V3) raises evidence Recall@5 by at least
10 points over V0 on jobs with four or more requirements (dev set, project-level evidence items).
*Refuted if* the gain on that slice is below 10 points.

**H-B2.** Hybrid BM25 plus dense retrieval (V2) beats dense-only V0 on nDCG@10 for every persona, because job posts
name exact tools ("Airflow", "dbt", "Power BI") that embeddings blur.
*Refuted if* V0 is better for any persona.

**H-B3.** Better retrieval does not translate one-for-one into replies: the GigSim reply-rate gain of the shipped
pipeline over V0 is smaller, in relative terms, than its Recall@5 gain, because simulated clients also weigh price,
generic openings and screening answers.

**H-B4 (claim verification).** Claim verification cuts unsupported claims per proposal by at least 50%.

## R&D question C: is the multi-agent design worth it?
**H-C.** On 50 dev jobs, the hand-built graph has higher bid-or-skip accuracy, fewer unsupported claims and fewer
policy violations in its final text than both a single ReAct agent holding all tools and the prebuilt supervisor.
The single ReAct agent uses the fewest tokens, and it can match the graph on simple, clearly relevant jobs where one
search finds the evidence.
*Refuted if* either baseline matches the graph on accuracy and unsupported claims together.

## Safety
**H-S.** With all defences on, the attack success rate on the planted-injection dev jobs is at most 5%, and at least
three times lower than with the defences off.

## Signature extension X2
**H-X2.** No direction is assumed: strategy A (problem first) and strategy B (credentials first) are compared with a
two-sided exact McNemar test on paired reply outcomes at the 5% level.

## Evaluation sizes (fixed on 14 Nov 2026, before the model-based runs)
The project runs on free tiers only, so the dev-set runs use the first N items of each persona's set in its fixed
file order (the sets were shuffled when built). Sizes were chosen from measured rate limits, not from results:
- Retrieval variants without a model step: 50 dev jobs per persona (150 jobs).
- Retrieval variants with a model step (V1, V6, V7, V8): 20 dev jobs per persona.
- Decisions (dev): 40 jobs per persona (120 jobs). Proposals (V0 vs shipped): 10 bid jobs per persona (30 pairs).
- Architecture comparison (question C): 30 dev jobs (10 per persona) instead of the brief's 50.
- X2 A/B test: 15 bid jobs per persona (45 paired proposals per arm).
- Injection: every planted-injection job in the dev sets, defences off and on.
- Model comparison (open vs open_gemma): 20 decisions and 4 proposals per persona.
- Holdout: all 50 jobs per persona for decisions; 10 per persona for proposals.
Latency is measured with several jobs in parallel on shared free-tier endpoints, so it includes waiting for rate
limits; the parallelism used is stored with each result.

## Budgets (declared in agent/config.yaml before the holdout run)
p95 latency per job analysed at most 20 s; p95 latency per proposal at most 90 s; cost per job analysed at most
US$0.002; cost per proposal at most US$0.01 (open profile).
