"""V8 corrective RAG as a small LangGraph: retrieve, grade the evidence per requirement, re-query when weak,
and refuse to claim a requirement when no evidence supports it (Yan et al., 2024)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agent.handoffs import EvidenceItem
from agent.prompts import load_prompt
from common.llm import complete, complete_json

NAME = "v8"
GROUP = "agentic"
MAX_REQUERIES = 1


class _Grades(BaseModel):
    relevant_ids: list[str] = Field(description="evidence ids that directly show the requirement")
    verdict: Literal["strong", "weak", "none"]


class CorrectiveState(TypedDict, total=False):
    requirement: str
    query: str
    attempts: int
    evidence: list[EvidenceItem]
    kept: list[EvidenceItem]
    verdict: str




def build_graph(search: Callable[[str], list[EvidenceItem]]):
    def retrieve(state: CorrectiveState) -> CorrectiveState:
        return {"evidence": search(state["query"]), "attempts": state.get("attempts", 0) + 1}

    def grade(state: CorrectiveState) -> CorrectiveState:
        if not state["evidence"]:
            return {"kept": [], "verdict": "none"}
        listing = "\n".join(f"[{e.evidence_id}] {e.title}: {e.text[:400]}" for e in state["evidence"])
        result = complete_json("rag_helper", load_prompt("rag_grade"),
                               f"Requirement: {state['requirement']}\n\nEvidence:\n{listing}", _Grades)
        keep = [e for e in state["evidence"] if e.evidence_id in set(result.relevant_ids)]
        return {"kept": keep, "verdict": result.verdict if keep else "none"}

    def rewrite(state: CorrectiveState) -> CorrectiveState:
        return {"query": complete("rag_helper", load_prompt("rag_rewrite"), state["requirement"],
                                  max_tokens=80).strip()}

    def route(state: CorrectiveState) -> str:
        if state["verdict"] == "strong" or state["attempts"] > MAX_REQUERIES:
            return END
        return "rewrite"

    graph = StateGraph(CorrectiveState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade", grade)
    graph.add_node("rewrite", rewrite)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", route, {"rewrite": "rewrite", END: END})
    graph.add_edge("rewrite", "retrieve")
    return graph.compile()


def correct(requirement: str, search: Callable[[str], list[EvidenceItem]]) -> tuple[list[EvidenceItem], str]:
    """Return (kept evidence, verdict). Verdict 'none' means: do not claim this requirement."""
    state = build_graph(search).invoke({"requirement": requirement, "query": requirement})
    return state.get("kept", []), state.get("verdict", "none")
