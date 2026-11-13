"""Pipeline board, analytics, memory viewer and health (degraded-mode banner)."""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException

from agent.mcp_client import server_health
from agent.memory.promotion_rules import pin_style_rule
from agent.memory.store import get_store
from apps.api.auth.users import CurrentUser
from apps.api.schemas.models import Health, MemoryItem, PinRuleIn, PipelineCard
from common import db
from common.config import load_config

router = APIRouter(prefix="/api", tags=["analytics"])
MEMORY_NAMESPACES = ("style", "style_candidates", "outcome")


@router.get("/pipeline", response_model=list[PipelineCard])
def pipeline(user: dict = CurrentUser) -> list[PipelineCard]:
    rows = db.fetch_all("SELECT proposal_id, job_id, title, stage, data, updated_at FROM pipeline_cards WHERE "
                        "user_id = %s ORDER BY updated_at DESC", (user["user_id"],))
    drafted = db.fetch_all("SELECT job_id, thread_id, summary, updated_at FROM jobs_seen WHERE user_id = %s AND "
                           "status = 'awaiting_approval'", (user["user_id"],))
    cards = [PipelineCard(proposal_id=f"draft-{r['job_id']}", job_id=r["job_id"], title=r["summary"].get("title", ""),
                          stage="drafted", updated_at=r["updated_at"].isoformat(),
                          data={"graph_thread_id": r["thread_id"]}) for r in drafted]
    cards += [PipelineCard(proposal_id=r["proposal_id"], job_id=r["job_id"], title=r["title"], stage=r["stage"],
                           updated_at=r["updated_at"].isoformat(), data=r["data"]) for r in rows]
    return cards


@router.get("/analytics")
def analytics(user: dict = CurrentUser) -> dict:
    uid = user["user_id"]
    cards = db.fetch_all("SELECT p.stage, p.data, j.summary FROM pipeline_cards p LEFT JOIN jobs_seen j ON "
                         "j.user_id = p.user_id AND j.job_id = p.job_id WHERE p.user_id = %s", (uid,))
    by_category: dict[str, Counter] = defaultdict(Counter)
    connects_by_outcome: Counter = Counter()
    for card in cards:
        category = ((card["summary"] or {}).get("job") or {}).get("category") or "other"
        stage = card["stage"]
        by_category[category]["sent"] += 1
        by_category[category]["replied"] += stage in ("replied", "interview", "hired")
        by_category[category]["hired"] += stage == "hired"
        connects_by_outcome[stage] += int((card["data"] or {}).get("connects", 0))
    rates = [{"category": c, "sent": v["sent"], "reply_rate": round(v["replied"] / v["sent"], 3),
              "hire_rate": round(v["hired"] / v["sent"], 3)} for c, v in sorted(by_category.items())]
    runs = db.fetch_all("SELECT kind, seconds, tokens, usd, status FROM run_metrics WHERE user_id = %s", (uid,))

    def percentile(values: list[float], q: float) -> float | None:
        if not values:
            return None
        values = sorted(values)
        return round(values[min(len(values) - 1, int(q * (len(values) - 1) + 0.5))], 3)

    analysed = [r for r in runs if r["kind"] == "bid"]
    proposals = [r for r in analysed if r["status"] in ("awaiting_approval", "submitted")]
    reasons = Counter(r["reason"].strip().lower()[:80] for r in
                      db.fetch_all("SELECT reason FROM approvals_log WHERE user_id = %s AND action = 'reject'", (uid,))
                      if r["reason"])
    declared = load_config()["budgets"]["declared"]
    return {
        "reply_and_hire_by_category": rates,
        "connects_by_outcome": dict(connects_by_outcome),
        "jobs_analysed": len(analysed),
        "cost_latency": {
            "per_job_analysed": {"p50_s": percentile([r["seconds"] for r in analysed], 0.5),
                                 "p95_s": percentile([r["seconds"] for r in analysed], 0.95),
                                 "mean_usd": round(sum(r["usd"] for r in analysed) / len(analysed), 6)
                                 if analysed else None},
            "per_proposal": {"p50_s": percentile([r["seconds"] for r in proposals], 0.5),
                             "p95_s": percentile([r["seconds"] for r in proposals], 0.95),
                             "mean_usd": round(sum(r["usd"] for r in proposals) / len(proposals), 6)
                             if proposals else None},
            "declared": declared,
        },
        "top_rejection_reasons": reasons.most_common(5),
    }


@router.get("/memory", response_model=list[MemoryItem])
def memory(user: dict = CurrentUser) -> list[MemoryItem]:
    store = get_store()
    return [MemoryItem(namespace=ns, key=item.key, value=item.value)
            for ns in MEMORY_NAMESPACES for item in store.search((ns, user["user_id"]), limit=100)]


@router.delete("/memory/{namespace}/{key}", status_code=204)
def forget(namespace: str, key: str, user: dict = CurrentUser) -> None:
    if namespace not in MEMORY_NAMESPACES:
        raise HTTPException(404, "unknown memory")
    get_store().delete((namespace, user["user_id"]), key)


@router.post("/memory/style", response_model=MemoryItem, status_code=201)
def pin(body: PinRuleIn, user: dict = CurrentUser) -> MemoryItem:
    store = get_store()
    key = pin_style_rule(store, user["user_id"], body.rule)
    return MemoryItem(namespace="style", key=key, value=store.get(("style", user["user_id"]), key).value)


@router.get("/health", response_model=Health)
async def health() -> Health:
    servers = await server_health()
    queued = db.fetch_one("SELECT count(*) AS n FROM jobs_seen WHERE status = 'needs_attention'")
    degraded = not all(servers.values())
    return Health(marketplace=servers.get("marketplace", False), servers=servers, degraded=degraded,
                  queued_jobs=int(queued["n"]) if queued else 0,
                  message="Marketplace unavailable: new work is queued and will resume automatically."
                  if not servers.get("marketplace", False) else "")
