"""Request and response models of the HTTP API (the TypeScript client is generated from these)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Persona = Literal["ai_ml_engineer", "fullstack_web_dev", "data_analyst"]


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    persona: Persona = "ai_ml_engineer"


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=200)  # an email, or a short demo username such as "admin"
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    user_id: str
    email: str
    display_name: str
    persona: str


class SessionOut(BaseModel):
    user: UserOut
    token: str


class SavedSearch(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    query: str = Field("", max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=10)
    category: str = Field("", max_length=80)
    every_hours: int = Field(4, ge=1, le=48)


class Rates(BaseModel):
    hourly_floor: float | None = Field(None, ge=0)
    fixed_floor: float | None = Field(None, ge=0)
    target_hourly_rate: float | None = Field(None, ge=0)


class Filters(BaseModel):
    min_budget: float = Field(0, ge=0)
    payment_types: list[Literal["fixed", "hourly"]] = Field(default_factory=lambda: ["fixed", "hourly"])


class SettingsModel(BaseModel):
    persona: Persona | None = None
    autonomy: Literal["suggest", "auto_skip_low_fit"] = "suggest"
    weekly_connects_budget: int = Field(80, ge=0, le=1000)
    auto_analyze_per_scout: int = Field(5, ge=0, le=50, description="Newest jobs analysed automatically per scout run")
    timezone: str = "Asia/Karachi"
    rates: Rates = Field(default_factory=Rates)
    saved_searches: list[SavedSearch] = Field(default_factory=list, max_length=20)
    filters: Filters = Field(default_factory=Filters)
    marketplace: Literal["gigsim", "upwork_live"] = "gigsim"


class InboxItem(BaseModel):
    job_id: str
    title: str
    status: str
    first_seen: str
    thread_id: str | None = None
    fit: float | None = None
    risk: float | None = None
    risk_flags: list[str] = Field(default_factory=list)
    client_quality: float | None = None
    action: str | None = None
    price: float | None = None
    payment_type: str | None = None
    connects_cost: int | None = None
    status_reason: str = ""
    budget_min: float | None = None
    budget_max: float | None = None
    skills: list[str] = Field(default_factory=list)


class JobDetail(BaseModel):
    job: dict[str, Any]
    thread_id: str | None = None
    status: str | None = None
    status_reason: str = ""
    job_spec: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    fit: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    decision: dict[str, Any] | None = None
    price: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None
    critiques: list[dict[str, Any]] = Field(default_factory=list)
    compliance: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    pending_approval: dict[str, Any] | None = None
    tokens: int = 0
    usd: float = 0.0
    trace: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalItem(BaseModel):
    thread_id: str
    kind: Literal["proposal", "message"]
    title: str
    created_at: str | None = None
    request: dict[str, Any]


class ApprovalIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: str | None = Field(None, max_length=6000)
    edited_answers: list[str] | None = None
    reason: str = Field("", max_length=500)


class RegenerateIn(BaseModel):
    paragraph_index: int = Field(ge=0, le=20)
    instruction: str = Field("", max_length=300)


class RegenerateOut(BaseModel):
    paragraph_index: int
    text: str


class Accepted(BaseModel):
    queued: bool = True
    thread_id: str
    detail: str = ""


class ThreadSummary(BaseModel):
    thread_id: str
    job_id: str = ""
    client_id: str = ""
    last_message_at: str | None = None
    unread: int = 0
    graph_thread_id: str
    status: str | None = None


class PipelineCard(BaseModel):
    proposal_id: str
    job_id: str
    title: str
    stage: Literal["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]
    updated_at: str
    data: dict[str, Any] = Field(default_factory=dict)


class MemoryItem(BaseModel):
    namespace: str
    key: str
    value: dict[str, Any]


class PinRuleIn(BaseModel):
    rule: str = Field(min_length=3, max_length=200)


class Health(BaseModel):
    api: bool = True
    marketplace: bool
    servers: dict[str, bool]
    degraded: bool
    queued_jobs: int = 0
    message: str = ""


class TraceStep(BaseModel):
    checkpoint_id: str
    next: list[str]
    status: str | None
    step: int | None
    created_at: str | None


class RunInfo(BaseModel):
    thread_id: str
    events: list[dict[str, Any]]
    trace_url: str | None = None
    history: list[TraceStep] = Field(default_factory=list)
