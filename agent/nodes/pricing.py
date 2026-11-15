"""Bid-or-skip decision (rules from config) and the Pricing Strategist."""
from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig

from agent.handoffs import BidDecision, FitReport, Job, PriceQuote, RiskReport
from agent.marketplace_port import MarketplacePort
from agent.nodes.base import ctx, node, persona_profile, tools_for
from agent.prompts import load_prompt
from common.config import defences_on, load_config, load_policy
from common.llm import complete_json


def decide(job: Job, risk: RiskReport, fit: FitReport, settings: dict[str, Any] | None = None) -> BidDecision:
    """Deterministic, explainable rules over the three analyses (thresholds in config, per-user overrides)."""
    t = {**load_config()["thresholds"], **(settings or {}).get("thresholds", {})}
    reasons: list[str] = []
    if risk.is_scam:
        reasons.append("risk: " + "; ".join(f"{f.kind} ('{f.evidence[:60]}')" for f in risk.flags[:3]))
        action = "skip"
    elif risk.injection_detected and defences_on():
        reasons.append("the post contains instructions aimed at automated tools; skipped for safety")
        action = "skip"
    elif risk.score > t["max_risk"]:
        reasons.append(f"risk score {risk.score:.2f} is above the limit {t['max_risk']}")
        action = "skip"
    elif fit.score < t["watch_min_fit"]:
        reasons.append(f"fit {fit.score:.2f} is below {t['watch_min_fit']}: the portfolio does not show enough of "
                       f"what the job needs (missing: {', '.join(fit.missing_skills[:4]) or 'core requirements'})")
        action = "skip"
    elif fit.score < t["bid_min_fit"] or risk.client_quality < t["min_client_quality"]:
        reasons.append(f"borderline: fit {fit.score:.2f}, client quality {risk.client_quality:.2f}")
        action = "watch"
    else:
        reasons.append(f"fit {fit.score:.2f} and risk {risk.score:.2f} are within limits")
        action = "bid"
    reasons += fit.reasons[:2]
    return BidDecision(job_id=job.job_id, action=action, reasons=reasons, fit_score=fit.score, risk_score=risk.score)


@node("decide")
async def decide_node(state: dict, config: RunnableConfig) -> dict:
    missing = [name for name, key in (("risk_assessor", "risk"), ("fit_matcher", "fit"), ("analyst", "job_spec"))
               if state.get(key) is None]
    if missing:      # a parallel branch failed: never decide on half an analysis, and say which branch it was
        return {"status": "dead_letter", "status_reason": f"analysis incomplete: {', '.join(missing)} failed"}
    decision = decide(state["job"], state["risk"], state["fit"], ctx(config).get("settings"))
    update: dict[str, Any] = {"decision": decision}
    if decision.action == "skip":
        update.update(status="skipped", status_reason="; ".join(decision.reasons[:2]))
    elif decision.action == "watch":
        update.update(status="watching", status_reason="; ".join(decision.reasons[:2]))
    return update


def connects_cost(job: Job, policy: dict[str, Any]) -> int:
    """Listed Connects cost plus any surcharge the current policy defines."""
    cost = job.connects_cost
    for surcharge in policy.get("connects", {}).get("surcharges", []):
        if surcharge.get("payment_type") in (None, job.payment_type) and \
                (job.budget_max or 0) >= surcharge.get("min_budget", float("inf")):
            cost += int(surcharge["extra"])
    return cost


def quote(job: Job, fit: FitReport, risk: RiskReport, market: dict, profile: dict, balance: dict,
          client_spent: float) -> PriceQuote:
    policy = load_policy()
    cost = connects_cost(job, policy)
    band = market.get(job.payment_type, {}) if isinstance(market.get(job.payment_type), dict) else {}
    floor = float(profile.get("hourly_floor" if job.payment_type == "hourly" else "fixed_floor", 0) or 0)
    user = (f"Job: {job.title}\npayment_type: {job.payment_type}; client budget: {job.budget_min} to "
            f"{job.budget_max}\nMarket for comparable jobs ({market.get('n', 0)} jobs): p25={band.get('p25')}, "
            f"p50={band.get('p50')}, p75={band.get('p75')}\nFreelancer floor: {floor}; target hourly rate: "
            f"{profile.get('target_hourly_rate')}\nFit score: {fit.score:.2f}; client quality "
            f"{risk.client_quality:.2f}; client total spent {client_spent}\nConnects cost: {cost}; balance: "
            f"{balance.get('balance')}; weekly budget left: {balance.get('weekly_budget_left')}")
    price = complete_json("pricing", load_prompt("pricing"), user, PriceQuote)
    price.job_id, price.payment_type, price.connects_cost, price.floor = job.job_id, job.payment_type, cost, floor
    price.market_p25, price.market_p50, price.market_p75 = band.get("p25"), band.get("p50"), band.get("p75")
    if price.amount < floor:  # the floor is a hard rule, whatever the model proposed
        price.amount = floor
        price.rationale += f" Raised to the freelancer's floor ({floor})."
    left = balance.get("weekly_budget_left")
    if left is not None and cost > left:
        price.connects_worth_it = False
        price.rationale += f" Not enough of the weekly Connects budget left ({left} < {cost})."
    return price


@node("pricing")
async def pricing(state: dict, config: RunnableConfig) -> dict:
    job: Job = state["job"]
    port = MarketplacePort(tools_for("pricing", config))
    market = await port.get_market_pricing(job.category, job.skills)
    balance = (await port.get_connects_balance()).model_dump()
    settings = ctx(config).get("settings") or {}
    profile = {**persona_profile(config["configurable"]["persona"]), **settings.get("rates", {})}
    if settings.get("weekly_connects_budget") is not None:
        balance["weekly_budget_left"] = min(balance.get("weekly_budget_left") or 10**6,
                                            settings["weekly_connects_budget"] - settings.get("connects_spent_week", 0))
    price = await asyncio.to_thread(quote, job, state["fit"], state["risk"], market, profile, balance, 0.0)
    update: dict[str, Any] = {"price": price}
    if not price.connects_worth_it:
        update.update(status="watching", status_reason=f"Connects not worth it: {price.rationale[:200]}")
    return update
