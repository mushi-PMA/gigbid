"""V0 baseline: fixed-size chunks, top-k cosine similarity on the whole job post."""
from __future__ import annotations

from rag.index.store import EvidenceIndex, Hit
from rag.variants.base import Query, dense_search

NAME = "v0"
GROUP = "baseline"


def queries(job_text: str, requirements: list[dict]) -> list[Query]:
    return [Query(job_text)]


def retrieve(index: EvidenceIndex, query: Query, k: int) -> list[Hit]:
    return dense_search(index, query, k)
