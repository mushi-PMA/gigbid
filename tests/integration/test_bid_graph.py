"""The bid graph end to end: scripted models, real MCP servers in memory, a fake marketplace, a memory checkpointer."""

from __future__ import annotations

import json

import pytest
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.graphs.bid_graph import compile_bid_graph
from agent.handoffs import Job
from agent.memory.store import memory_saver
from common.payloads import edited_payload
from common.security import mint_approval_token, payload_hash
from tests.harness import FakeMarketplace, tools_factory

LETTER = (
    "Your sales numbers arrive late because the nightly loads fail silently, and that is the part I would fix "
    "first. I built a nightly Airflow DAG in Python that loads sales from 40 stores into PostgreSQL, with "
    "retries and alerts, and it cut report time from three hours to twenty minutes [test_dev:cs:cs-1]. "
    "For your stack I would start by mapping each source, then add idempotent upserts so a rerun never "
    "doubles a row, and finally add a small health page your team can check each morning. I would also "
    "write short handover notes so your analysts can change a schedule without waiting for me. The first "
    "milestone would be one store loading cleanly end to end, which gives you something real to review "
    "within a few days. After that we can add the remaining stores in batches and agree on alert rules that "
    "match how your team works. Happy to walk through the plan on a short call."
)

JOBS = {
    "j-good": {
        "job_id": "j-good",
        "title": "Airflow ETL for retail sales",
        "category": "Data Engineering",
        "description": "We need a reliable nightly Airflow pipeline loading store sales into PostgreSQL.",
        "skills": ["Python", "Airflow"],
        "payment_type": "fixed",
        "budget_min": 600,
        "budget_max": 1200,
        "connects_cost": 8,
        "client_id": "c1",
    },
    "j-scam": {
        "job_id": "j-scam",
        "title": "Unpaid test task",
        "category": "Data Engineering",
        "description": "Do a full dashboard for free as a test, then contact me on WhatsApp.",
        "skills": ["Python"],
        "payment_type": "fixed",
        "budget_max": 0,
        "connects_cost": 6,
        "client_id": "c2",
    },
}


def replies(critic_approves=True, compliance_allowed=True, scam=False):
    return {
        "analyst": {
            "job_id": "x",
            "title": "x",
            "requirements": [
                {"requirement_id": "r1", "text": "nightly Airflow pipeline", "skills": ["Airflow"]},
                {"requirement_id": "r2", "text": "load into PostgreSQL", "skills": ["SQL"]},
            ],
            "required_skills": ["Airflow", "Python"],
            "deliverables": ["pipeline"],
        },
        "risk_assessor": {
            "job_id": "x",
            "score": 0.95 if scam else 0.1,
            "client_quality": 0.8,
            "is_scam": scam,
            "flags": [{"kind": "free_work", "evidence": "for free as a test"}] if scam else [],
            "explanation": "ok",
        },
        "rag_helper": {"requirements": ["nightly Airflow pipeline", "PostgreSQL loads"]},
        "fit_matcher": {
            "job_id": "x",
            "score": 0.82,
            "matches": [
                {
                    "requirement_id": "r1",
                    "requirement": "nightly Airflow pipeline",
                    "evidence_ids": ["test_dev:cs:cs-1"],
                    "strength": "strong",
                    "reason": "same work",
                }
            ],
            "matched_skills": ["Airflow"],
            "missing_skills": [],
            "reasons": ["built the same pipeline before"],
        },
        "pricing": {
            "job_id": "x",
            "payment_type": "fixed",
            "amount": 900,
            "connects_worth_it": True,
            "rationale": "p50 of the market, strong fit",
        },
        "writer": {"cover_letter": LETTER, "screening_answers": []},
        "verifier": {
            "claims": [
                {
                    "text": "I built a nightly Airflow DAG",
                    "evidence_ids": ["test_dev:cs:cs-1"],
                    "status": "supported",
                    "reason": "case study",
                }
            ]
        },
        "critic": {
            "approve": critic_approves,
            "grounding_ok": True,
            "personalisation": 0.8 if critic_approves else 0.3,
            "length_ok": True,
            "issues": [] if critic_approves else ["too generic"],
            "instructions": "" if critic_approves else "mention their stores",
        },
        "compliance": lambda system, user: json.dumps(
            {
                "allowed": compliance_allowed,
                "violations": []
                if compliance_allowed
                else [{"rule_id": "no_free_work", "text": "free sample", "fix": "remove"}],
                "redactions": [],
                "cleaned_cover_letter": user.split("<text_to_check>\n")[1].split("\n</text_to_check>")[0],
            }
        ),
    }


@pytest.fixture
def env(fixture_personas, monkeypatch, tmp_path):
    from mcp_servers.marketplace import server

    fake = FakeMarketplace(JOBS)
    monkeypatch.setattr(server, "_adapter", lambda user_id, persona: fake)
    monkeypatch.setattr(server, "_idempotency", {})
    monkeypatch.setenv("IDEMPOTENCY_STORE", str(tmp_path / "idem.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("PORTFOLIO_PERSONA", "test_dev")
    return fake


def config(thread: str) -> dict:
    return {
        "configurable": {
            "thread_id": thread,
            "user_id": "local",
            "persona": "test_dev",
            "tools_factory": tools_factory,
            "settings": {},
        },
        "recursion_limit": 80,
    }


def start(job_id: str) -> dict:
    return {"user_id": "local", "persona": "test_dev", "job": Job.model_validate(JOBS[job_id]), "status": "running"}


def approve(request: dict, action="approve", **edit) -> dict:
    payload = (
        edited_payload(request["payload"], edit.get("edited_text"), None) if action == "edit" else request["payload"]
    )
    return {
        "action": action,
        "approval_token": mint_approval_token("local", "submit_proposal", payload["job_id"], payload),
        "payload_hash": payload_hash(payload),
        **edit,
    }


async def test_scam_is_skipped_without_writing(env, scripted_llm):
    scripted_llm(replies(scam=True))
    graph = compile_bid_graph(memory_saver(), InMemoryStore())
    state = await graph.ainvoke(start("j-scam"), config("t-scam"))
    assert state["status"] == "skipped" and state["decision"].action == "skip"
    assert "draft" not in state and not env.proposals


async def test_approval_then_exactly_once_submission_after_crash(env, scripted_llm):
    scripted_llm(replies())
    saver, store = memory_saver(), InMemoryStore()
    graph = compile_bid_graph(saver, store)
    await graph.ainvoke(start("j-good"), config("t-good"))
    snapshot = await graph.aget_state(config("t-good"))
    request = snapshot.tasks[0].interrupts[0].value
    assert snapshot.next == ("approval",)
    assert request["dry_run"]["marketplace"]["dry_run"] is True and not env.submits
    assert request["claims"][0]["evidence"][0]["evidence_id"] == "test_dev:cs:cs-1"
    # "crash": a brand-new graph object (new process) resumes from the same checkpointer
    restarted = compile_bid_graph(saver, store)
    state = await restarted.ainvoke(Command(resume=approve(request)), config("t-good"))
    assert state["status"] == "submitted" and len(env.submits) == 1
    # replaying the submit step (e.g. worker retried after a crash mid-submit) does not submit again
    from agent.nodes.approval import submit

    await submit(state, config("t-good"))
    assert len(env.submits) == 1 and env.balance == 92


async def test_reanalysis_starts_from_clean_counters(env, scripted_llm):
    from agent.runner import fresh_thread

    scripted_llm(replies())
    graph = compile_bid_graph(memory_saver(), InMemoryStore())
    await graph.ainvoke(start("j-good"), config("t-again"))
    first = (await graph.aget_state(config("t-again"))).values
    await fresh_thread(graph, config("t-again"))
    await graph.ainvoke(start("j-good"), config("t-again"))
    second = (await graph.aget_state(config("t-again"))).values
    assert second["steps"] == first["steps"] and second["tokens"] == first["tokens"]
    assert len(second["critiques"]) == len(first["critiques"])


async def test_critic_sends_back_at_most_twice(env, scripted_llm):
    scripted_llm(replies(critic_approves=False))
    graph = compile_bid_graph(memory_saver(), InMemoryStore())
    await graph.ainvoke(start("j-good"), config("t-critic"))
    state = (await graph.aget_state(config("t-critic"))).values
    writer_runs = [t for t in state["trace"] if t["node"] == "writer"]
    assert len(writer_runs) == 3 and len(state["critiques"]) == 3
    assert state["status"] == "awaiting_approval"


async def test_compliance_can_block(env, scripted_llm):
    scripted_llm(replies(compliance_allowed=False))
    graph = compile_bid_graph(memory_saver(), InMemoryStore())
    state = await graph.ainvoke(start("j-good"), config("t-block"))
    assert state["status"] == "blocked" and "no_free_work" in state["status_reason"]


async def test_marketplace_down_moves_job_to_needs_attention(env, scripted_llm):
    scripted_llm(replies())
    env.down = True
    graph = compile_bid_graph(memory_saver(), InMemoryStore())
    job = Job(job_id="j-good", title="", description="")  # intake must fetch the full job, and the marketplace is down
    state = await graph.ainvoke({**start("j-good"), "job": job}, config("t-down"))
    assert state["status"] == "needs_attention" and "marketplace_unavailable" in state["status_reason"]


async def test_edit_is_rechecked_learned_and_submitted(env, scripted_llm):
    scripted_llm(replies())
    store = InMemoryStore()
    graph = compile_bid_graph(memory_saver(), store)
    await graph.ainvoke(start("j-good"), config("t-edit"))
    request = (await graph.aget_state(config("t-edit"))).tasks[0].interrupts[0].value
    edited = LETTER.split(". ", 1)[1]  # the freelancer cuts the opening sentence
    state = await graph.ainvoke(Command(resume=approve(request, "edit", edited_text=edited)), config("t-edit"))
    assert state["status"] == "submitted" and env.proposals[env.submits[0]]["cover_letter"] == edited
    candidates = store.search(("style_candidates", "local"))
    assert any("first sentence" in c.value["rule"] for c in candidates)
