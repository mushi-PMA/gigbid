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

## Budgets (declared in agent/config.yaml before the holdout run)
p95 latency per job analysed at most 20 s; p95 latency per proposal at most 90 s; cost per job analysed at most
US$0.002; cost per proposal at most US$0.01 (open profile).
