"""GigSim REST API (see gigsim/API.md). Build the app with create_app(); settings come from environment variables."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

from gigsim import clients, policy
from gigsim.faults import FaultInjector, RateLimiter
from gigsim.store import Store, fmt, parse

ROOT = Path(__file__).resolve().parents[1]
JOB_FIELDS = ["job_id", "title", "description", "skills", "category", "payment_type", "budget_min", "budget_max",
              "experience_level", "connects_cost", "client_id", "posted_at", "applicants", "screening_questions", "url"]
STATUS_OF_EVENT = {"proposal_viewed": "viewed", "client_replied": "replied", "interview_requested": "interview",
                   "hired": "hired", "declined": "declined"}
STATUS_RANK = ["submitted", "viewed", "replied", "interview", "hired"]
MAX_CLIENT_MESSAGES = 6


@dataclass
class Settings:
    db_path: str
    seed_dir: Path
    error_rate: float
    rate_limit: int
    start: datetime
    speed: float
    admin_token: str
    llm: bool
    seed: int

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            db_path=env.get("GIGSIM_DB", str(ROOT / "data" / "gigsim" / "gigsim.db")),
            seed_dir=Path(env.get("GIGSIM_SEED_DIR", str(ROOT / "data" / "gigsim"))),
            error_rate=float(env.get("GIGSIM_ERROR_RATE", "0.02")),
            rate_limit=int(env.get("GIGSIM_RATE_LIMIT_PER_MIN", "60")),
            start=parse(env.get("GIGSIM_START", "2026-10-27T00:00:00Z")),
            speed=float(env.get("GIGSIM_SPEED", "1.0")),
            admin_token=env.get("GIGSIM_ADMIN_TOKEN", ""),
            llm=env.get("GIGSIM_LLM", "off").lower() == "on",
            seed=int(env.get("GIGSIM_SEED", "2026")),
        )


class Clock:
    """Simulated time: starts at GIGSIM_START and runs at GIGSIM_SPEED times real time (0 freezes it)."""

    def __init__(self, start: datetime, speed: float):
        self.speed = speed
        self.set(start)

    def set(self, moment: datetime) -> None:
        self._sim, self._real = moment, time.monotonic()

    def now(self) -> datetime:
        return self._sim + timedelta(seconds=(time.monotonic() - self._real) * self.speed)


class AnswerIn(BaseModel):
    question: str = ""
    answer: str = ""


class ProposalIn(BaseModel):
    job_id: str
    cover_letter: str = Field(min_length=1)
    screening_answers: list[AnswerIn] = Field(default_factory=list)
    bid_amount: float = Field(ge=0)
    payment_type: Literal["fixed", "hourly"] | None = None


class MessageIn(BaseModel):
    text: str = Field(min_length=1)


class ClockIn(BaseModel):
    now: str


class GrantIn(BaseModel):
    account_id: str
    amount: int


def public_job(job: dict) -> dict:
    """Only the marketplace fields. Labels such as `kind` and `source` stay inside GigSim."""
    return {key: job.get(key) for key in JOB_FIELDS}


def error(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.db_path, settings.seed_dir, settings.seed)
    clock = Clock(settings.start, settings.speed)
    limiter = RateLimiter(settings.rate_limit)
    faults = FaultInjector(settings.error_rate, settings.seed)
    pricing_path = settings.seed_dir / "pricing.json"
    pricing = json.loads(pricing_path.read_text(encoding="utf-8")) if pricing_path.exists() else {}

    tokens: dict[str, dict] = {}
    for account in store.accounts():
        token = os.environ.get(account["env_token"] or "") or account["token"]
        tokens[token] = account

    app = FastAPI(title="GigSim", version="1.0")
    app.state.store, app.state.clock, app.state.settings = store, clock, settings

    def now_iso() -> str:
        return fmt(clock.now())

    # ---- guard: auth, rate limit, fault injection ------------------------------------------------------
    @app.middleware("http")
    async def guard(request: Request, call_next):
        if not request.url.path.startswith("/v1"):
            return await call_next(request)
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        account = next((a for t, a in tokens.items() if hmac.compare_digest(t, token)), None) if token else None
        if account is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        wait = limiter.check(token)
        if wait is not None:
            return JSONResponse({"error": "rate limit exceeded", "retry_after": wait}, status_code=429,
                                headers={"Retry-After": str(wait)})
        dry = request.query_params.get("dry_run", "").lower() in ("1", "true", "yes")
        has_key = request.method == "POST" and not dry and bool(request.headers.get("idempotency-key"))
        fault = faults.draw(has_key)
        if fault == "before":
            return JSONResponse({"error": "temporarily unavailable"}, status_code=503)
        request.state.account = account
        response = await call_next(request)
        if fault == "after" and response.status_code < 400:  # the write happened, the answer is lost
            return JSONResponse({"error": "temporarily unavailable"}, status_code=503)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = [{"where": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse({"error": "invalid request", "violations": details}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    # ---- helpers ---------------------------------------------------------------------------------------
    def view_proposal(p: dict) -> dict:
        status = p["status"]
        if status != "draft":
            due = [STATUS_OF_EVENT[t] for t in store.due_event_types(p["proposal_id"], now_iso()) if t in STATUS_OF_EVENT]
            status = "declined" if "declined" in due else max(["submitted"] + due, key=STATUS_RANK.index)
        shown = {k: v for k, v in p.items() if k != "account_id"}
        shown["status"] = status
        if shown["thread_id"] and not store.list_messages(shown["thread_id"], now_iso(), mark_read=False):
            shown["thread_id"] = None  # the thread is not visible yet
        return shown

    def own_proposal(request: Request, proposal_id: str) -> dict:
        found = store.get_proposal(proposal_id)
        if not found or found["account_id"] != request.state.account["account_id"]:
            raise HTTPException(404, "proposal not found")
        return found

    def write(request: Request, body: dict, action: Callable[[bool], tuple[int, dict]]) -> JSONResponse:
        """Run a write with dry_run and Idempotency-Key handling. Only successful results are remembered."""
        dry = request.query_params.get("dry_run", "").lower() in ("1", "true", "yes")
        key = request.headers.get("idempotency-key")
        if dry or not key:
            status, result = action(dry)
            return JSONResponse(result, status_code=status)
        account_id = request.state.account["account_id"]
        fingerprint = hashlib.sha256(json.dumps([request.method, request.url.path, body], sort_keys=True).encode()).hexdigest()
        with store.transaction():
            found = store.get_idempotent(account_id, key)
            if found:
                if found["fingerprint"] != fingerprint:
                    return error(409, "Idempotency-Key was already used for a different request")
                return JSONResponse(json.loads(found["body"]), status_code=found["status"],
                                    headers={"Idempotent-Replay": "true"})
            status, result = action(False)
            if status < 400:
                store.put_idempotent(account_id, key, fingerprint, status, result)
        return JSONResponse(result, status_code=status)

    # ---- open endpoints --------------------------------------------------------------------------------
    @app.get("/health")
    def health():
        now = clock.now()
        return {"status": "ok", "now": fmt(now), "policy_version": policy.version_at(now)}

    @app.post("/admin/clock")
    def set_clock(request: Request, body: ClockIn):
        require_admin(request)
        try:
            clock.set(parse(body.now))
        except ValueError:
            raise HTTPException(422, "now must be an ISO time")
        return {"now": now_iso(), "policy_version": policy.version_at(clock.now())}

    @app.post("/admin/connects")
    def grant_connects(request: Request, body: GrantIn):
        require_admin(request)
        if not any(a["account_id"] == body.account_id for a in store.accounts()):
            raise HTTPException(404, "account not found")
        return {"balance": store.add_connects(body.account_id, body.amount, now_iso(), "grant")}

    def require_admin(request: Request) -> None:
        header = request.headers.get("authorization", "")
        given = header[7:].strip() if header.lower().startswith("bearer ") else ""
        if not settings.admin_token:
            raise HTTPException(403, "admin endpoints are disabled (set GIGSIM_ADMIN_TOKEN)")
        if not hmac.compare_digest(given, settings.admin_token):
            raise HTTPException(401, "bad admin token")

    # ---- read endpoints --------------------------------------------------------------------------------
    @app.get("/v1/jobs")
    def list_jobs(q: str = "", skills: str = "", category: str = "", since: str = "", limit: int = 50, offset: int = 0):
        try:
            since_text = fmt(parse(since)) if since else ""
        except ValueError:
            raise HTTPException(422, "since must be an ISO time")
        wanted = [s.strip() for s in skills.split(",") if s.strip()]
        jobs, total = store.search_jobs(now_iso(), q, wanted, category, since_text, max(1, min(limit, 200)), max(0, offset))
        return {"jobs": [public_job(j) for j in jobs], "total": total}

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str):
        job = store.get_job(job_id, now_iso())
        if not job:
            raise HTTPException(404, "job not found")
        return public_job(job)

    @app.get("/v1/clients/{client_id}")
    def get_client(client_id: str):
        client = store.get_client(client_id)
        if not client:
            raise HTTPException(404, "client not found")
        return client["public"]  # hidden preferences are never exposed

    @app.get("/v1/connects")
    def connects(request: Request):
        account = request.state.account
        now = clock.now()
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        weekly = account["weekly_budget"]
        left = None if weekly is None else max(0, weekly - store.spent_since(account["account_id"], fmt(week_start)))
        return {"balance": store.balance(account["account_id"]), "weekly_budget_left": left}

    @app.get("/v1/proposals")
    def list_proposals(request: Request):
        return {"proposals": [view_proposal(p) for p in store.list_proposals(request.state.account["account_id"])]}

    @app.get("/v1/proposals/{proposal_id}")
    def get_proposal(request: Request, proposal_id: str):
        return view_proposal(own_proposal(request, proposal_id))

    @app.get("/v1/threads")
    def list_threads(request: Request):
        return {"threads": store.list_threads(request.state.account["account_id"], now_iso())}

    def own_thread(request: Request, thread_id: str) -> dict:
        thread = store.get_thread(thread_id)
        visible = thread and store.list_messages(thread_id, now_iso(), mark_read=False)
        if not thread or thread["account_id"] != request.state.account["account_id"] or not visible:
            raise HTTPException(404, "thread not found")
        return thread

    @app.get("/v1/threads/{thread_id}/messages")
    def list_messages(request: Request, thread_id: str):
        own_thread(request, thread_id)
        return {"messages": store.list_messages(thread_id, now_iso())}

    @app.get("/v1/events")
    def list_events(request: Request, since: str = ""):
        try:
            since_text = fmt(parse(since)) if since else ""
        except ValueError:
            raise HTTPException(422, "since must be an ISO time")
        return {"events": store.list_events(request.state.account["account_id"], since_text, now_iso())}

    @app.get("/v1/policy")
    def get_policy():
        return policy.policy_document(clock.now())

    @app.get("/v1/market/pricing")
    def market_pricing(category: str = "", skills: str = ""):
        wanted = [s.strip().lower() for s in skills.split(",") if s.strip()]
        by_skill = {name.lower(): stats for name, stats in pricing.get("skills", {}).items()}
        categories = {name.lower(): (name, stats) for name, stats in pricing.get("categories", {}).items()}
        chosen, basis = None, "all"
        candidates = [by_skill[s] for s in wanted if s in by_skill]
        if candidates:
            chosen, basis = max(candidates, key=lambda s: s["n"]), "skills"
        elif category.lower() in categories:
            chosen, basis = categories[category.lower()][1], "category"
        chosen = chosen or pricing.get("all") or {"n": 0, "fixed": {}, "hourly": {}}

        def band(stats: dict) -> dict:
            return {k: stats.get(k) for k in ("p25", "p50", "p75")}

        return {"category": category or None, "basis": basis, "n": chosen["n"], "fixed": band(chosen["fixed"]),
                "hourly": band(chosen["hourly"])}

    # ---- write endpoints -------------------------------------------------------------------------------
    @app.post("/v1/proposals")
    def create_proposal(request: Request, body: ProposalIn):
        account = request.state.account

        def action(dry: bool) -> tuple[int, dict]:
            job = store.get_job(body.job_id, now_iso())
            if not job:
                return 404, {"error": "job not found"}
            existing = store.find_proposal_for_job(account["account_id"], body.job_id)
            if existing:
                return 409, {"error": "a proposal for this job already exists", "proposal_id": existing["proposal_id"]}
            answers = [a.model_dump() for a in body.screening_answers]
            payment_type = body.payment_type or job["payment_type"]
            if dry:
                preview = {"proposal_id": None, "job_id": body.job_id, "status": "draft", "cover_letter": body.cover_letter,
                           "screening_answers": answers, "bid_amount": body.bid_amount, "payment_type": payment_type}
                return 200, {"dry_run": True, "proposal": preview, "connects_cost": 0,
                             "note": "A draft costs no Connects. Submitting spends them."}
            created = store.create_proposal(account["account_id"], body.job_id, body.cover_letter, answers,
                                            body.bid_amount, payment_type, now_iso())
            return 201, view_proposal(created)

        return write(request, body.model_dump(), action)

    @app.post("/v1/proposals/{proposal_id}/submit")
    def submit_proposal(request: Request, proposal_id: str):
        account = request.state.account
        proposal = own_proposal(request, proposal_id)

        def action(dry: bool) -> tuple[int, dict]:
            current = store.get_proposal(proposal_id)
            if current["status"] != "draft":
                return 409, {"error": "proposal was already submitted"}
            job = store.get_job(current["job_id"], include_history=False)
            now = clock.now()
            version = policy.version_at(now)
            found = policy.violations(current["cover_letter"], current["screening_answers"], now)
            if found:
                return 422, {"error": "policy violation", "policy_version": version, "violations": found}
            cost = policy.connects_cost(job, now)
            balance = store.balance(account["account_id"])
            if balance < cost:
                return 402, {"error": "not enough Connects", "needed": cost, "balance": balance}
            if dry:
                return 200, {"dry_run": True, "would_submit": True, "proposal_id": proposal_id, "connects_cost": cost,
                             "balance_before": balance, "balance_after": balance - cost, "policy_version": version}
            with store.transaction():
                new_balance = store.add_connects(account["account_id"], -cost, fmt(now), "proposal", proposal_id)
                thread_id = schedule_outcome(account["account_id"], job, current, now)
                store.mark_submitted(proposal_id, fmt(now), cost, version, thread_id)
            result = view_proposal(store.get_proposal(proposal_id))
            result["balance"] = new_balance
            return 200, result

        return write(request, {"proposal_id": proposal["proposal_id"]}, action)

    def schedule_outcome(account_id: str, job: dict, proposal: dict, now: datetime) -> str | None:
        """Let the simulated client decide, then put the outcomes on the timeline as future events and messages."""
        client = store.get_client(job["client_id"]) or {"hidden": {}}
        hidden = client["hidden"]
        kind = job.get("kind", "regular")
        decision = clients.decide(hidden, job, proposal, kind)
        digest = clients.proposal_hash(job["client_id"], job["job_id"], proposal)
        if settings.llm and kind == "regular":
            cached = store.cached_decision(digest)
            if cached:
                decision = clients.Decision(**cached)
            else:
                verdict = clients.llm_decision(hidden, job, proposal, decision.score)
                if verdict:
                    decision = clients.apply_verdict(decision, verdict)
                    store.cache_decision(digest, {"score": decision.score, "viewed": decision.viewed,
                                                  "replied": decision.replied, "interview": decision.interview,
                                                  "hired": decision.hired, "declined": decision.declined,
                                                  "reply_text": decision.reply_text, "used_llm": True})
        pace = hidden.get("responsiveness", "normal")
        at, thread_id = now, None
        base = {"client_id": job["client_id"], "job_id": job["job_id"]}
        thread_kind = kind if kind in ("scam", "injection") else "proposal"

        def step(stage: str) -> datetime:
            return at + timedelta(hours=clients.delay_hours(pace, digest, stage))

        def say(stage: str, when: datetime, text: str, event_type: str, extra: dict) -> None:
            nonlocal thread_id
            if thread_id is None:
                thread_id = store.create_thread(account_id, job["job_id"], job["client_id"], thread_kind,
                                                proposal["proposal_id"])
            message_id = store.add_message(thread_id, "client", text, fmt(when))
            store.add_event(account_id, event_type, proposal["proposal_id"], thread_id, fmt(when),
                            {**base, "message_id": message_id, **extra})

        if decision.viewed:
            at = step("viewed")
            store.add_event(account_id, "proposal_viewed", proposal["proposal_id"], None, fmt(at), base)
        if decision.replied:
            at = step("replied")
            text = decision.reply_text or clients.reply_text("replied", job, hidden, proposal, kind, digest)
            say("replied", at, text, "client_replied", {})
        if decision.interview:
            at = step("interview")
            say("interview", at, clients.reply_text("interview", job, hidden, proposal, kind, digest),
                "interview_requested", {"proposed_slots": clients.slots(fmt(at), digest)})
        if decision.hired:
            at = step("hired")
            say("hired", at, clients.reply_text("hired", job, hidden, proposal, kind, digest), "hired",
                {"amount": proposal["bid_amount"], "payment_type": proposal["payment_type"]})
        if decision.declined:
            at = step("declined")
            say("declined", at, clients.reply_text("declined", job, hidden, proposal, kind, digest), "declined",
                {"reason": "another candidate was chosen"})
        return thread_id

    @app.post("/v1/threads/{thread_id}/messages")
    def send_message(request: Request, thread_id: str, body: MessageIn):
        account = request.state.account
        thread = own_thread(request, thread_id)

        def action(dry: bool) -> tuple[int, dict]:
            now = now_iso()
            job_id = thread["job_id"]
            if dry:
                return 200, {"dry_run": True, "message": {"message_id": None, "thread_id": thread_id, "job_id": job_id,
                                                          "sender": "freelancer", "text": body.text, "sent_at": now}}
            with store.transaction():
                message_id = store.add_message(thread_id, "freelancer", body.text, now)
                count = store.client_message_count(thread_id)
                if count < MAX_CLIENT_MESSAGES:
                    job = store.get_job(job_id, include_history=True) or {"title": ""}
                    client = store.get_client(thread["client_id"]) or {"hidden": {}}
                    key = f"{thread_id}-{message_id}"
                    when = parse(now) + timedelta(hours=clients.delay_hours(
                        client["hidden"].get("responsiveness", "normal"), key, "msg"))
                    reply_id = store.add_message(thread_id, "client", clients.thread_reply(
                        thread["kind"], job["title"], count, key), fmt(when))
                    store.add_event(account["account_id"], "client_replied", thread["proposal_id"], thread_id, fmt(when),
                                    {"client_id": thread["client_id"], "job_id": job_id, "message_id": reply_id})
            return 200, {"message_id": message_id, "thread_id": thread_id, "job_id": job_id, "sender": "freelancer",
                         "text": body.text, "sent_at": now}

        return write(request, body.model_dump(), action)

    return app
