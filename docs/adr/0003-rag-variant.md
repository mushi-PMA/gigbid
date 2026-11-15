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

**Decision.** `rag.variant: v2_v4`: hybrid BM25 + dense retrieval with the outcome-aware boost. V2+V4+V7 retrieves
better (nDCG@10 0.629 against 0.587 on the same 60 jobs), but HyDE adds one model call per search, about 40% of the
tokens of a whole job analysis. The binding constraint for this project turned out to be free-tier tokens per day
(Groq: 200,000 per model per key), not dollars, so we ship the variant without a model step and keep V7 as the
first upgrade once a paid or local model is available (a one-line change). The Fit Matcher still decomposes each post
into requirements itself (V1 at the node level) and runs the searches in parallel.

**Consequences.** No CPU-bound rerank and no extra model calls in retrieval, so analysis is faster and cheaper on the
2-vCPU server; we give up about 0.04 nDCG@10. V8 (corrective loop) was measured later on 30 dev jobs
(`evals/results/rag_variants_model_late.json`): V2+V8 nDCG@10 0.558 against 0.530 for V2 and 0.612 for V2+V4 on the
same 30 jobs, at 21.7 s per search on average, so it does not change the decision. V6 (contextual chunks) needs a model
call per chunk at index time and was not run within the free-tier budget; see docs/RESULTS.md.
