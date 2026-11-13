# ADR 0003: Shipped RAG variant chosen by measurement

Status: accepted

**Context.** R6: the deployed retrieval design is chosen by evaluation, not by default.

**Decision.** `rag.variant` in `agent/config.yaml` is set to the variant with the best evidence Recall@5 and nDCG@10
on the dev set that also keeps p95 retrieval latency within budget (`evals/results/rag_variants*.json`), confirmed by
the proposal-level comparison against V0 (`proposals_v0.json`, `proposals_best.json`).

**Consequences.** Changing the variant is a one-line config change, and the CI smoke evaluation fails if evidence
recall drops below its threshold.
