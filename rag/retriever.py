"""Retriever factory: the variant pipeline is chosen by config (`rag.variant`), e.g. "v0" or "v1+v2+v3+v5".

Order of stages: queries (V1 decomposition or the whole post) -> HyDE expansion (V7) -> per-query retrieval
(dense, or V2 hybrid) -> V3 rerank -> fuse queries -> V4 outcome boost -> V5 project grouping -> V8 corrective loop.
V6 is an index-time variant: it selects the index built with context lines.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.handoffs import EvidenceItem
from common.config import load_config
from common.tracing import span
from rag.index.store import EvidenceIndex, Hit, build_index
from rag.variants import (v0_naive, v1_decomposition, v2_hybrid, v3_rerank, v4_outcome, v5_multivector,
                          v6_contextual, v7_hyde, v8_corrective)
from rag.variants.base import Query, rrf, to_items

KNOWN = {"v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"}


@dataclass
class RetrievalResult:
    items: list[EvidenceItem]
    per_requirement: dict[str, list[EvidenceItem]] = field(default_factory=dict)
    refused: list[str] = field(default_factory=list)      # requirement ids with no supporting evidence (V8)
    queries: list[str] = field(default_factory=list)


def parse_variant(spec: str) -> set[str]:
    parts = {p.strip().lower() for p in spec.replace("_", "+").split("+") if p.strip()}
    unknown = parts - KNOWN
    if unknown:
        raise ValueError(f"unknown RAG variant(s): {sorted(unknown)}")
    return parts or {"v0"}


_index_cache: dict[str, EvidenceIndex] = {}


def get_index(persona: str, contextual: bool = False) -> EvidenceIndex:
    name = f"{persona}__ctx" if contextual else persona
    if name not in _index_cache:
        index = EvidenceIndex.load(name)
        if index is None:
            from rag.ingest.loaders import load_persona

            index = build_index(name, load_persona(persona),
                                contextualize=v6_contextual.contextualize if contextual else None)
            index.save()
        _index_cache[name] = index
    return _index_cache[name]


def invalidate(persona: str) -> None:
    _index_cache.pop(persona, None)
    _index_cache.pop(f"{persona}__ctx", None)


class Retriever:
    def __init__(self, persona: str, variant: str | None = None, k: int | None = None):
        self.persona = persona
        self.variant = variant or load_config()["rag"]["variant"]
        self.parts = parse_variant(self.variant)
        self.k = k or load_config()["rag"]["top_k"]
        self.index = get_index(persona, contextual="v6" in self.parts)

    # One query through retrieval, rerank, boost and grouping.
    def _search_query(self, query: Query, pool: int) -> list[Hit]:
        hits = v2_hybrid.retrieve(self.index, query, pool) if "v2" in self.parts else \
            v0_naive.retrieve(self.index, query, pool)
        if "v3" in self.parts:
            hits = v3_rerank.rerank(query, hits)
        return hits

    def _finish(self, hits: list[Hit], limit: int) -> list[EvidenceItem]:
        if "v4" in self.parts:
            hits = v4_outcome.boost(self.index, hits)
        if "v5" in self.parts:
            hits = v5_multivector.group_by_project(self.index, hits)
        return to_items(hits, self.persona, limit)

    def search_text(self, text: str, k: int | None = None) -> list[EvidenceItem]:
        """Single free-text search (used by the Portfolio MCP tool and the corrective loop)."""
        k = k or self.k
        return self._finish(self._search_query(Query(text), max(30, k * 3)), k)

    def retrieve(self, job_text: str, requirements: list[dict] | None = None, k: int | None = None) \
            -> RetrievalResult:
        k = k or self.k
        with span("rag.retrieve", kind="RETRIEVER", variant=self.variant, persona=self.persona):
            queries = v1_decomposition.queries(job_text, requirements or []) if "v1" in self.parts \
                else v0_naive.queries(job_text, [])
            if "v7" in self.parts:
                queries = v7_hyde.expand(queries)
            pool = max(30, k * 3)
            per_query = [(q, self._search_query(q, pool)) for q in queries]
            merged = per_query[0][1] if len(per_query) == 1 else rrf([hits for _, hits in per_query], limit=pool * 2)
            result = RetrievalResult(items=self._finish(merged, k), queries=[q.text for q in queries])
            if len(per_query) > 1:
                result.per_requirement = {q.requirement_id: self._finish(hits, 4) for q, hits in per_query}
            if "v8" in self.parts:
                for query in queries:
                    kept, verdict = v8_corrective.correct(query.text, lambda text: self.search_text(text, 5))
                    result.per_requirement[query.requirement_id] = kept
                    if verdict == "none":
                        result.refused.append(query.requirement_id)
                supported = [e for q in queries for e in result.per_requirement.get(q.requirement_id, [])]
                seen: set[str] = set()
                result.items = [e for e in supported + result.items
                                if not (e.evidence_id in seen or seen.add(e.evidence_id))][:k]
            return result
