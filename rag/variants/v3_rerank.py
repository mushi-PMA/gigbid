"""V3 cross-encoder reranking of the candidate pool (open reranker on CPU, set in config)."""
from __future__ import annotations

from rag.index.embeddings import rerank_scores
from rag.index.store import Hit
from rag.variants.base import Query

NAME = "v3"
GROUP = "retrieval"
POOL = 30


def rerank(query: Query, hits: list[Hit]) -> list[Hit]:
    pool = hits[:POOL]
    if not pool:
        return hits
    scores = rerank_scores(query.text, [h.chunk.indexed_text[:1500] for h in pool])
    reranked = sorted((Hit(h.chunk, s) for h, s in zip(pool, scores)), key=lambda h: h.score, reverse=True)
    return reranked + hits[POOL:]
