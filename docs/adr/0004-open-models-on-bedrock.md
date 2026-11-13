# ADR 0004: Open-weight models through a hosted provider; routed by node

Status: accepted

**Context.** The deployed link must work on the open profile, and free hosts have no GPU.

**Decision.** The `open` profile uses open-weight models through Amazon Bedrock: gpt-oss-20b for frequent, cheap nodes
and gpt-oss-120b for the Writer, Critic and Client Liaison. `open_local` runs Qwen3 through Ollama (compose service);
`open_qwen` is the second open configuration compared on the dev set. Embeddings and the reranker are open models on
CPU (fastembed, ONNX). Every node's model is set in config.

**Consequences.** One client (`common/llm.py`) handles Bedrock and any OpenAI-compatible server, with metering,
retries, a fallback model for cheap nodes and a disk cache for evaluation reruns.
