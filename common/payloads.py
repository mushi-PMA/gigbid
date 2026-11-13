"""The exact payload a human approves and the marketplace receives (shared by the graph, the API and the MCP
server, so the approval token always signs the same bytes)."""
from __future__ import annotations

from typing import Any


def draft_payload(job_id: str, cover_letter: str, screening_answers: list[dict], bid_amount: float,
                  payment_type: str) -> dict[str, Any]:
    return {"job_id": job_id, "cover_letter": cover_letter, "screening_answers": screening_answers,
            "bid_amount": round(float(bid_amount), 2), "payment_type": payment_type}


def edited_payload(payload: dict[str, Any], edited_text: str | None, edited_answers: list[str] | None) \
        -> dict[str, Any]:
    answers = [dict(a) for a in payload["screening_answers"]]
    for answer, text in zip(answers, edited_answers or []):
        answer["answer"] = text or answer["answer"]
    return draft_payload(payload["job_id"], edited_text or payload["cover_letter"], answers, payload["bid_amount"],
                         payload["payment_type"])
