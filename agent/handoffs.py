"""Typed hand-off objects that agents exchange.

Every value a later step decides on travels as one of these Pydantic models, never as free text.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------------------------------------
# Marketplace objects (returned by the marketplace port, identical for GigSim and live Upwork)
# ---------------------------------------------------------------------------------------------------------


class Job(BaseModel):
    job_id: str
    title: str
    description: str
    skills: list[str] = Field(default_factory=list)
    category: str = ""
    payment_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: float | None = None
    budget_max: float | None = None
    experience_level: str = ""
    connects_cost: int = 0
    client_id: str = ""
    posted_at: datetime | None = None
    applicants: str = ""
    screening_questions: list[str] = Field(default_factory=list)
    url: str = ""


class ClientHistory(BaseModel):
    client_id: str
    country: str = ""
    payment_verified: bool = False
    total_spent: float = 0.0
    hires: int = 0
    jobs_posted: int = 0
    rating: float | None = None
    reviews_count: int = 0
    member_since: str = ""
    recent_feedback: list[str] = Field(default_factory=list)


class ConnectsBalance(BaseModel):
    balance: int
    weekly_budget_left: int | None = None


class Message(BaseModel):
    message_id: str
    thread_id: str
    job_id: str = ""
    sender: Literal["client", "freelancer"]
    text: str
    sent_at: datetime | None = None


# ---------------------------------------------------------------------------------------------------------
# Analysis hand-offs
# ---------------------------------------------------------------------------------------------------------


class Requirement(BaseModel):
    requirement_id: str
    text: str
    skills: list[str] = Field(default_factory=list)


class JobSpec(BaseModel):
    job_id: str
    title: str
    summary: str = ""
    deliverables: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    payment_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: float | None = None
    budget_max: float | None = None
    timeline: str = ""
    screening_questions: list[str] = Field(default_factory=list)
    hidden_needs: list[str] = Field(default_factory=list)


RiskKind = Literal[
    "scam", "free_work", "off_platform", "injection", "payment_unverified", "low_budget", "duplicate", "other"
]


class RiskFlag(BaseModel):
    kind: RiskKind
    evidence: str


class RiskReport(BaseModel):
    job_id: str
    score: float = Field(ge=0, le=1, description="0 = safe, 1 = certain scam or abuse")
    client_quality: float = Field(ge=0, le=1)
    is_scam: bool = False
    injection_detected: bool = False
    flags: list[RiskFlag] = Field(default_factory=list)
    explanation: str = ""


class EvidenceItem(BaseModel):
    evidence_id: str
    persona: str
    type: Literal["cv", "case_study", "readme", "code", "review", "proposal"]
    project: str = ""
    title: str = ""
    text: str
    skills: list[str] = Field(default_factory=list)
    date: str = ""
    client_industry: str = ""
    outcome: str = ""
    source: str = ""
    score: float = 0.0


class RequirementMatch(BaseModel):
    requirement_id: str
    requirement: str
    evidence_ids: list[str] = Field(default_factory=list)
    strength: Literal["strong", "partial", "none"] = "none"
    reason: str = ""


class FitReport(BaseModel):
    job_id: str
    score: float = Field(ge=0, le=1)
    matches: list[RequirementMatch] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class BidDecision(BaseModel):
    job_id: str
    action: Literal["bid", "watch", "skip"]
    reasons: list[str] = Field(default_factory=list)
    fit_score: float = 0.0
    risk_score: float = 0.0


class PriceQuote(BaseModel):
    job_id: str
    payment_type: Literal["fixed", "hourly"]
    amount: float
    market_p25: float | None = None
    market_p50: float | None = None
    market_p75: float | None = None
    floor: float = 0.0
    connects_cost: int = 0
    connects_worth_it: bool = True
    rationale: str = ""


# ---------------------------------------------------------------------------------------------------------
# Writing hand-offs
# ---------------------------------------------------------------------------------------------------------

ClaimStatus = Literal["supported", "partly_supported", "unsupported"]


class Claim(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: ClaimStatus = "unsupported"
    reason: str = ""


class ScreeningAnswer(BaseModel):
    question: str
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)


class ProposalDraft(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    revision: int = 0
    unsupported_before_verification: int = 0
    unsupported_after_verification: int = 0


class Critique(BaseModel):
    approve: bool
    grounding_ok: bool = True
    personalisation: float = Field(default=0.0, ge=0, le=1)
    length_ok: bool = True
    issues: list[str] = Field(default_factory=list)
    instructions: str = ""


class Violation(BaseModel):
    rule_id: str
    text: str
    fix: str = ""


class ComplianceVerdict(BaseModel):
    allowed: bool
    blocked_reason: str = ""
    violations: list[Violation] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)
    cleaned_cover_letter: str = ""


# ---------------------------------------------------------------------------------------------------------
# Conversations and approvals
# ---------------------------------------------------------------------------------------------------------

Intent = Literal["question", "negotiation", "interview_request", "scam_signal", "other"]


class MessageAnalysis(BaseModel):
    thread_id: str
    intent: Intent
    injection_detected: bool = False
    summary: str = ""


class ReplyDraft(BaseModel):
    thread_id: str
    text: str
    proposed_slots: list[str] = Field(default_factory=list)
    email_draft_id: str = ""


class ApprovalDecision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: str = ""
    reason: str = ""
    user_id: str = ""
