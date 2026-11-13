# ADR 0006: Postgres with pgvector, and self-hosted Arize Phoenix for traces

Status: accepted

**Context.** We need a checkpointer, a memory store, a vector store and tracing, with as few services as possible.

**Decision.** One Postgres (pgvector image) holds checkpoints, the LangGraph store, evidence vectors, app tables and
the audit log. Arize Phoenix runs self-hosted (OTLP) and stores its data in the same Postgres.

**Consequences.** One database to back up. Offline evaluation and tests use the in-memory equivalents with the same
ranking (exact cosine), so results transfer.
