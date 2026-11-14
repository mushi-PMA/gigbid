# ADR 0004: Open-weight models from a pool of hosted endpoints; routed by node

Status: accepted (revised: the first version used one cloud provider whose model access was never granted)

**Context.** The deployed link must work on the open profile, free hosts have no GPU, and the project has no budget
for paid APIs. Each free tier alone is too small for the evaluations (Groq's free tier, measured: 1,000 requests a
day and 8,000 tokens a minute on gpt-oss-20b).

**Decision.** The `open` profile asks for a model *size* per node (`small` = gpt-oss-20b for frequent, cheap nodes;
`large` = gpt-oss-120b for the Writer, Critic and Client Liaison). `models.endpoints` lists hosted endpoints and the
exact model id each one serves for a size. A call goes to the next endpoint with a key that serves the size; one that
returns a rate limit rests until its `retry-after` passes. Every endpoint for a size serves the same open weights, so
results do not depend on which one answered (the served model id is still recorded per call). `open_gemma` (Gemma 4)
is the second open configuration compared on the dev set; `open_local` runs Qwen3 through Ollama. Embeddings and the
reranker are open models on CPU (fastembed, ONNX). Every node's model is set in config.

**Consequences.** Free tiers add up instead of capping the run, and losing one provider degrades speed, not
correctness. Providers can differ slightly in serving details (quantisation, context limits); this is a known source
of noise we accept. Cost is reported at list price for the same weights because the actual bill is US$0.