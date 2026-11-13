"""Conversation graph (one thread per client conversation).

load_messages -> classify_intent (question | negotiation | interview_request | scam_signal | other)
-> draft_reply (evidence and calendar slots through MCP) -> Compliance check -> human approval (interrupt)
-> approve: send (exactly once) and place tentative holds | edit: learn style, re-check, send or ask again | reject.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes.base import is_stopped
from agent.nodes.liaison import (
    after_check,
    after_reply_approval,
    check_reply,
    classify_intent,
    draft_reply,
    load_messages,
    reply_approval,
    send,
)
from agent.state import ConversationState


def _continue(next_node: str):
    return lambda state: END if is_stopped(state) else next_node


def build_conversation_graph() -> StateGraph:
    graph = StateGraph(ConversationState)
    graph.add_node("load_messages", load_messages)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("draft_reply", draft_reply)
    graph.add_node("check_reply", check_reply)
    graph.add_node("reply_approval", reply_approval)
    graph.add_node("send", send)
    graph.add_edge(START, "load_messages")
    graph.add_conditional_edges("load_messages", _continue("classify_intent"), ["classify_intent", END])
    graph.add_conditional_edges("classify_intent", _continue("draft_reply"), ["draft_reply", END])
    graph.add_conditional_edges("draft_reply", _continue("check_reply"), ["check_reply", END])
    graph.add_conditional_edges("check_reply", after_check, {"end": END, "send": "send",
                                                             "reply_approval": "reply_approval"})
    graph.add_conditional_edges("reply_approval", after_reply_approval,
                                {"end": END, "check_reply": "check_reply", "send": "send"})
    graph.add_edge("send", END)
    return graph


def compile_conversation_graph(checkpointer=None, store=None):
    return build_conversation_graph().compile(checkpointer=checkpointer, store=store)
