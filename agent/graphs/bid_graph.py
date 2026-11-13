"""Bid graph (one thread per job), hand-written StateGraph.

intake -> [Job Analyst | Risk Assessor | Fit Matcher] in parallel (Send) -> decide (skip | watch | bid)
-> Pricing Strategist -> Proposal Writer -> claim verification -> Critic (back to Writer at most twice)
-> Compliance Guard (can block) -> dry-run preview -> human approval (interrupt)
-> approve: submit (exactly once) | edit: learn style, re-check Compliance, then submit or ask again | reject: end.
Step and token budgets move a thread to `needs_attention`; failures go to `dead_letter`.
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.nodes.analyst import job_analyst
from agent.nodes.approval import (after_approval, after_edit_check, approval, learn_from_edit, prepare_approval,
                                  submit)
from agent.nodes.base import is_stopped, over_budget
from agent.nodes.compliance import compliance
from agent.nodes.critic import after_critic, critic
from agent.nodes.matcher import fit_matcher
from agent.nodes.pricing import decide_node, pricing
from agent.nodes.risk import risk_assessor
from agent.nodes.scout import intake
from agent.nodes.writer import verifier, writer
from agent.state import BidState


async def needs_attention(state: dict, config: RunnableConfig) -> dict:
    return {"status": "needs_attention", "status_reason": over_budget(state) or state.get("status_reason", "")}


def _stop_or(next_node: str):
    """Route to END when a node stopped the thread, to needs_attention when a budget is exceeded, else onward."""
    def route(state: dict) -> str:
        if is_stopped(state):
            return END
        if over_budget(state):
            return "needs_attention"
        return next_node
    return route


def fan_out(state: dict):
    if is_stopped(state):
        return END
    return [Send("analyst", state), Send("risk_assessor", state), Send("fit_matcher", state)]


def after_decide(state: dict) -> str:
    if is_stopped(state) or state["decision"].action != "bid":
        return END
    return "pricing"


def after_critic_route(state: dict) -> str:
    if is_stopped(state):
        return END
    if over_budget(state):
        return "needs_attention"
    return after_critic(state)


def after_compliance(state: dict) -> str:
    if is_stopped(state):
        return END
    if (state.get("approval") or {}).get("action") == "edit":
        return after_edit_check(state)
    return "prepare_approval"


def build_bid_graph() -> StateGraph:
    graph = StateGraph(BidState)
    graph.add_node("intake", intake)
    graph.add_node("analyst", job_analyst)
    graph.add_node("risk_assessor", risk_assessor)
    graph.add_node("fit_matcher", fit_matcher)
    graph.add_node("decide", decide_node)
    graph.add_node("pricing", pricing)
    graph.add_node("writer", writer)
    graph.add_node("verifier", verifier)
    graph.add_node("critic", critic)
    graph.add_node("compliance", compliance)
    graph.add_node("prepare_approval", prepare_approval)
    graph.add_node("approval", approval)
    graph.add_node("learn_from_edit", learn_from_edit)
    graph.add_node("submit", submit)
    graph.add_node("needs_attention", needs_attention)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", fan_out, ["analyst", "risk_assessor", "fit_matcher", END])
    for branch in ("analyst", "risk_assessor", "fit_matcher"):
        graph.add_edge(branch, "decide")
    graph.add_conditional_edges("decide", after_decide, ["pricing", END])
    graph.add_conditional_edges("pricing", _stop_or("writer"), ["writer", "needs_attention", END])
    graph.add_conditional_edges("writer", _stop_or("verifier"), ["verifier", "needs_attention", END])
    graph.add_conditional_edges("verifier", _stop_or("critic"), ["critic", "needs_attention", END])
    graph.add_conditional_edges("critic", after_critic_route, ["writer", "compliance", "needs_attention", END])
    graph.add_conditional_edges("compliance", after_compliance, ["prepare_approval", "submit", END])
    graph.add_conditional_edges("prepare_approval", _stop_or("approval"), ["approval", "needs_attention", END])
    graph.add_conditional_edges("approval", after_approval,
                                {"end": END, "learn_from_edit": "learn_from_edit", "submit": "submit"})
    graph.add_edge("learn_from_edit", "compliance")
    graph.add_edge("submit", END)
    graph.add_edge("needs_attention", END)
    return graph


def compile_bid_graph(checkpointer=None, store=None):
    return build_bid_graph().compile(checkpointer=checkpointer, store=store)
