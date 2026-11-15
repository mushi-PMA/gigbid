"""Risk Assessor: client quality from history, plus scam, free-work, off-platform and injection flags.

Pattern rules from the policy pack run first (cheap, deterministic); the small model then confirms or rejects them
and looks for what patterns miss. Pattern hits for injection always stay flagged, whatever the model says.
"""
from __future__ import annotations

import asyncio

from langchain_core.runnables import RunnableConfig

from agent.handoffs import ClientHistory, Job, RiskFlag, RiskReport
from agent.marketplace_port import MarketplacePort
from agent.mcp_client import ToolError
from agent.nodes.analyst import job_metadata
from agent.nodes.base import node, tools_for
from agent.nodes.guards import delimit, injection_signals, scam_signals
from agent.prompts import load_prompt
from common.llm import complete_json


def client_quality(history: ClientHistory | None) -> float:
    """0 to 1 from public signals; a new client with no history scores about 0.3."""
    if history is None:
        return 0.3
    score = 0.25 if history.payment_verified else 0.0
    score += min(history.total_spent, 20000) / 20000 * 0.30
    score += min(history.hires, 20) / 20 * 0.20
    if history.rating is not None:
        score += max(0.0, (history.rating - 3.0) / 2.0) * 0.25
    else:
        score += 0.08
    return round(min(1.0, score), 3)


def assess(job: Job, history: ClientHistory | None) -> RiskReport:
    text = f"{job.title}\n{job.description}"
    scam_hits, injection_hits = scam_signals(text), injection_signals(text)
    history_text = history.model_dump_json() if history else "no history available"
    user = (f"Job metadata (trusted):\n{job_metadata(job)}\n\nClient history (trusted):\n{history_text}\n\n"
            f"Pattern rule hits: scam={scam_hits or 'none'}; injection={injection_hits or 'none'}\n\n"
            f"Job post (untrusted):\n{delimit('job_post', job.description)}")
    report = complete_json("risk_assessor", load_prompt("risk_assessor"), user, RiskReport)
    report.job_id = job.job_id
    report.client_quality = client_quality(history)
    if injection_hits and not report.injection_detected:
        report.injection_detected = True
        report.flags.append(RiskFlag(kind="injection", evidence=injection_hits[0]))
    if scam_hits and not report.is_scam:     # a scam pattern is decisive, like an injection pattern
        report.is_scam = True
        report.flags.append(RiskFlag(kind="scam", evidence=scam_hits[0]))
    if report.is_scam:
        report.score = max(report.score, 0.8)
    if history is not None and not history.payment_verified and \
            not any(f.kind == "payment_unverified" for f in report.flags):
        report.flags.append(RiskFlag(kind="payment_unverified", evidence="client payment method not verified"))
    if report.injection_detected:
        report.score = max(report.score, 0.7)
    return report


@node("risk_assessor")
async def risk_assessor(state: dict, config: RunnableConfig) -> dict:
    job: Job = state["job"]
    history = None
    if job.client_id:
        try:
            history = await MarketplacePort(tools_for("risk_assessor", config)).get_client_history(job.client_id)
        except ToolError:
            history = None  # unknown client: judged as new
    return {"risk": await asyncio.to_thread(assess, job, history)}
