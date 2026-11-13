"""V2 hybrid retrieval: BM25 and dense, merged with reciprocal rank fusion.

BM25 keeps exact tool and library names ("Celery", "dbt", "Pinecone") that embeddings blur.
"""
from __future__ import annotations

from rag.index.store import EvidenceIndex, Hit
from rag.variants.base import Query, dense_search, rrf

NAME = "v2"
GROUP = "retrieval"


def retrieve(index: EvidenceIndex, query: Query, k: int) -> list[Hit]:
    pool = max(k * 3, 30)
    return rrf([dense_search(index, query, pool), index.sparse(query.text, pool)], limit=pool)
