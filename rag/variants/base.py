"""Shared pieces for the retrieval variants: candidate lists, reciprocal rank fusion, doc-level collapsing."""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.handoffs import EvidenceItem
from rag.index.store import EvidenceIndex, Hit


@dataclass
class Query:
    text: str
    requirement_id: str = "job"
    vector_text: str = ""       # HyDE: text embedded for the dense search instead of `text`


@dataclass
class Candidates:
    """Scored chunks for one query (higher is better)."""
    query: Query
    hits: list[Hit] = field(default_factory=list)


def rrf(lists: list[list[Hit]], k: int = 60, limit: int = 50) -> list[Hit]:
    """Reciprocal rank fusion of ranked hit lists (Cormack et al., 2009)."""
    scores: dict[str, float] = {}
    chunk_by_id = {}
    for hits in lists:
        for rank, hit in enumerate(hits):
            cid = hit.chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            chunk_by_id[cid] = hit.chunk
    order = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [Hit(chunk_by_id[c], scores[c]) for c in order]


def to_items(hits: list[Hit], persona: str, limit: int) -> list[EvidenceItem]:
    """Collapse chunk hits to evidence documents (best chunk per document), keeping rank order."""
    seen: dict[str, EvidenceItem] = {}
    for hit in hits:
        meta = hit.chunk.metadata
        if hit.chunk.evidence_id in seen:
            continue
        seen[hit.chunk.evidence_id] = EvidenceItem(
            evidence_id=hit.chunk.evidence_id, persona=persona, type=meta.get("type", "case_study"),
            project=meta.get("project", ""), title=meta.get("title", ""), text=hit.chunk.text,
            skills=meta.get("skills", []), date=str(meta.get("date", "")),
            client_industry=meta.get("client_industry", ""), outcome=meta.get("outcome", ""),
            source=meta.get("source", ""), score=round(hit.score, 4))
        if len(seen) >= limit:
            break
    return list(seen.values())


def dense_search(index: EvidenceIndex, query: Query, k: int) -> list[Hit]:
    if query.vector_text:
        from rag.index.embeddings import embed

        vector = embed([query.vector_text])[0]  # a hypothetical document is embedded as a document
        return index.dense(query.text, k, query_vector=vector)
    return index.dense(query.text, k)
