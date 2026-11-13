"""V4 outcome-aware ranking: boost evidence from proposals that won or got replies, and the projects they used.

Weights are set in config (`rag.outcome_weights`) and can be learned from outcome memory (agent/memory).
"""
from __future__ import annotations

from common.config import load_config
from rag.index.store import EvidenceIndex, Hit

NAME = "v4"
GROUP = "ranking"
DEFAULT_WEIGHTS = {"won": 0.30, "replied": 0.15, "ignored": -0.20}


def _weights() -> dict[str, float]:
    return {**DEFAULT_WEIGHTS, **load_config()["rag"].get("outcome_weights", {})}


def project_outcome_scores(index: EvidenceIndex) -> dict[str, float]:
    """Mean outcome weight of past proposals per project (projects used in won proposals score high)."""
    weights = _weights()
    totals: dict[str, list[float]] = {}
    for chunk in index.chunks:
        meta = chunk.metadata
        if meta.get("type") == "proposal" and meta.get("project") and chunk.chunk_id.endswith("#0"):
            totals.setdefault(meta["project"], []).append(weights.get(meta.get("outcome", ""), 0.0))
    return {p: sum(v) / len(v) for p, v in totals.items()}


def boost(index: EvidenceIndex, hits: list[Hit]) -> list[Hit]:
    """Multiply relevance by (1 + outcome boost); works on any score scale because ranks are recomputed."""
    if not hits:
        return hits
    weights = _weights()
    by_project = getattr(index, "_outcome_cache", None)
    if by_project is None:
        by_project = project_outcome_scores(index)
        index._outcome_cache = by_project  # type: ignore[attr-defined]
    top = max(abs(h.score) for h in hits) or 1.0
    boosted = []
    for hit in hits:
        meta = hit.chunk.metadata
        bonus = weights.get(meta.get("outcome", ""), 0.0) if meta.get("type") == "proposal" else 0.0
        bonus += 0.5 * by_project.get(meta.get("project", ""), 0.0)
        boosted.append(Hit(hit.chunk, hit.score / top * (1.0 + bonus)))
    return sorted(boosted, key=lambda h: h.score, reverse=True)
