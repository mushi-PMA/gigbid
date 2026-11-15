"""Proposal routes (layout from the brief). Approve, edit and reject live in `approvals.py` with the other human
decisions, and so does paragraph regeneration (`POST /api/proposals/{thread_id}/regenerate`); proposal stages are in
`analytics.py` (`GET /api/pipeline`)."""
from apps.api.routers.approvals import regenerate_paragraph

__all__ = ["regenerate_paragraph"]
