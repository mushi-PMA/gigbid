"""Conversation graph: an interview request gets slots, waits for approval, then is sent once with holds placed."""
from __future__ import annotations

from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.graphs.conversation_graph import compile_conversation_graph
from agent.memory.store import memory_saver
from common.security import mint_approval_token, payload_hash
from tests.harness import tools_factory
from tests.integration.test_bid_graph import env  # noqa: F401  (fixture)


def config(thread: str) -> dict:
    return {"configurable": {"thread_id": thread, "user_id": "local", "persona": "test_dev",
                             "tools_factory": tools_factory, "settings": {"timezone": "UTC"}}}


async def test_interview_request_flow(env, scripted_llm, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setenv("WORKSPACE_DB", str(tmp_path / "ws.db"))
    scripted_llm({
        "intent": {"thread_id": "t1", "intent": "interview_request", "injection_detected": False,
                   "summary": "client wants a call"},
        "client_liaison": {"thread_id": "t1", "text": "Happy to talk. Do any of these times work for you?"},
        "compliance": lambda system, user: ('{"allowed": true, "violations": [], "redactions": [], '
                                            '"cleaned_cover_letter": "Happy to talk. Do any of these times work for '
                                            'you?"}'),
    })
    graph = compile_conversation_graph(memory_saver(), InMemoryStore())
    start = {"user_id": "local", "persona": "test_dev", "thread_id": "t1", "status": "running"}
    await graph.ainvoke(start, config("c1"))
    snapshot = await graph.aget_state(config("c1"))
    request = snapshot.tasks[0].interrupts[0].value
    assert request["analysis"]["intent"] == "interview_request" and request["reply"]["proposed_slots"]
    assert not env.sent
    payload = request["payload"]
    decision = {"action": "approve", "payload_hash": payload_hash(payload),
                "approval_token": mint_approval_token("local", "send_message", "t1", payload)}
    state = await graph.ainvoke(Command(resume=decision), config("c1"))
    assert state["status"] == "sent" and len(env.sent) == 1 and state["sent"]["holds"]
