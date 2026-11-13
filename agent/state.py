"""Typed graph state.

Three things are kept apart:
- State (this module): what one job or one conversation needs right now.
- Execution trace: every tool call, argument, result and observation, stored in `trace` (append-only reducer) and in
  the tracing backend (Phoenix) and the MCP audit log. It is for audit and debugging, never read by prompts.
- Long-term memory: promoted knowledge only, in the LangGraph store (agent/memory), written by explicit rules.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from agent.handoffs import (
    BidDecision,
    ComplianceVerdict,
    Critique,
    EvidenceItem,
    FitReport,
    Job,
    JobSpec,
    Message,
    MessageAnalysis,
    PriceQuote,
    ProposalDraft,
    ReplyDraft,
    RiskReport,
)


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


def add_tokens(left: int | None, right: int | None) -> int:
    return (left or 0) + (right or 0)


def latest(left: Any, right: Any) -> Any:
    """Last non-empty write wins (parallel branches may both report a status in the same step)."""
    return right if right not in (None, "") else left


ThreadStatus = Literal["running", "skipped", "watching", "awaiting_approval", "approved", "submitted", "rejected",
                       "blocked", "needs_attention", "dead_letter", "sent"]


class BidState(TypedDict, total=False):
    # inputs
    user_id: str
    persona: str
    job: Job
    # parallel analyses (each branch writes its own key; `errors` and `trace` use reducers)
    job_spec: JobSpec
    risk: RiskReport
    fit: FitReport
    evidence: list[EvidenceItem]
    # decision and pricing
    decision: BidDecision
    price: PriceQuote
    # writing loop
    draft: ProposalDraft
    critiques: Annotated[list[Critique], operator.add]
    revision: int
    compliance: ComplianceVerdict
    # approval and outcome
    approval: dict[str, Any]
    dry_run_preview: dict[str, Any]
    submission: dict[str, Any]
    status: Annotated[ThreadStatus, latest]
    status_reason: Annotated[str, latest]
    # bookkeeping
    steps: Annotated[int, add_tokens]
    tokens: Annotated[int, add_tokens]
    usd: Annotated[float, operator.add]
    errors: Annotated[list[str], operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]


class ConversationState(TypedDict, total=False):
    user_id: str
    persona: str
    thread_id: str
    job_id: str
    messages: list[Message]
    analysis: MessageAnalysis
    reply: ReplyDraft
    compliance: ComplianceVerdict
    approval: dict[str, Any]
    sent: dict[str, Any]
    status: Annotated[ThreadStatus, latest]
    status_reason: Annotated[str, latest]
    steps: Annotated[int, add_tokens]
    tokens: Annotated[int, add_tokens]
    usd: Annotated[float, operator.add]
    errors: Annotated[list[str], operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]
