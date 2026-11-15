# ADR 0003: Shipped RAG variant chosen by measurement

Status: accepted (14 to 15 Nov 2026, from the dev-set runs below)

**Context.** R6: the deployed retrieval design is chosen by evaluation, not by default. The first configuration was
`v1_v2_v3` (decomposition, hybrid, cross-encoder rerank), picked from the literature before any measurement.

**Measurements** (dev set, project-level evidence items; `evals/results/rag_variants_offline.json` on 150 jobs and
`evals/results/rag_variants_model.json` on 60 jobs):
- The cross-encoder reranker (V3) made retrieval *worse* on every combination (V2 nDCG@10 0.576 vs V2+V3 0.543) and
  was by far the slowest step (p95 17 to 40 s on a laptop CPU). On the 2-vCPU server it also starved the Portfolio
  MCP server until connections timed out. Our reading: an MS MARCO reranker scores web-passage relevance, while our
  corpus mixes code, READMEs and proposals whose wording differs from the job post's.
- Multi-vector project grouping (V5) also hurt (V2+V5 nDCG@10 0.460).
- Outcome-aware boosting (V4) helped (V2+V4 0.597 on 150 jobs) and HyDE (V7) helped more (V2+V4+V7 0.629 on 60 jobs,
  Recall@5 0.489).

**Decision.** `rag.variant: v2_v4_v7`: hybrid BM25 + dense retrieval, outcome-aware boost, and a hypothetical-answer
query (one small-model call per search, about US$0.0001 per job at list price). The Fit Matcher still decomposes
each post into requirements itself (V1 at the node level) and runs the searches in parallel.

**Consequences.** Better evidence and no CPU-bound rerank on the server, at the cost of one model call per search.
Changing the variant is a one-line config change. V6 and V8 finish later on the same 60 jobs; if either beats V7 by a
clear margin, this record is revised.
