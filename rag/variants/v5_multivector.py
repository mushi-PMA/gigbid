"""V5 multi-vector items: summary, README and code chunks are indexed separately and returned as one project.

A repo whose README looks irrelevant can still be found through its code; the project then returns all of its
evidence documents together, best-matching document first.
"""
from __future__ import annotations

from rag.index.store import EvidenceIndex, Hit

NAME = "v5"
GROUP = "indexing"


def group_by_project(index: EvidenceIndex, hits: list[Hit]) -> list[Hit]:
    """Order hits project by project (project score = best chunk + 0.1 per extra document type that matched)."""
    projects: dict[str, list[Hit]] = {}
    loose: list[Hit] = []
    for hit in hits:
        project = hit.chunk.metadata.get("project")
        (projects.setdefault(project, []) if project else loose).append(hit)
    scored = []
    for project, group in projects.items():
        types = {h.chunk.metadata.get("type") for h in group}
        scored.append((max(h.score for h in group) * (1 + 0.1 * (len(types) - 1)), group))
    scored += [(h.score, [h]) for h in loose]
    scored.sort(key=lambda item: item[0], reverse=True)
    ordered: list[Hit] = []
    for score, group in scored:
        # Best document of the project first, then its other evidence documents (one chunk each).
        seen_docs = set()
        for hit in sorted(group, key=lambda h: h.score, reverse=True):
            if hit.chunk.evidence_id not in seen_docs:
                seen_docs.add(hit.chunk.evidence_id)
                ordered.append(Hit(hit.chunk, score))
    return ordered
