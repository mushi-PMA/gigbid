"""Claim verification (B3): split a proposal into claims, check each against retrieved evidence, then remove or
rewrite unsupported claims before the Critic sees the draft. Reports unsupported claims before and after."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from agent.handoffs import Claim, EvidenceItem, ProposalDraft
from agent.prompts import load_prompt
from common.llm import complete, complete_json
from common.tracing import span

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


class _Verified(BaseModel):
    claims: list[Claim] = Field(description="every factual claim about the freelancer, in order")


def _verify_system() -> str:
    return load_prompt("verify_claims")


def _rewrite_system() -> str:
    return load_prompt("verify_rewrite")


def _evidence_listing(evidence: list[EvidenceItem]) -> str:
    return "\n".join(f"[{e.evidence_id}] ({e.type}) {e.title}: {e.text[:700]}" for e in evidence)


def verify_text(text: str, evidence: list[EvidenceItem]) -> list[Claim]:
    if not text.strip():
        return []
    user = f"<evidence>\n{_evidence_listing(evidence)}\n</evidence>\n\n<proposal>\n{text}\n</proposal>"
    known = {e.evidence_id for e in evidence}
    claims = complete_json("verifier", _verify_system(), user, _Verified, max_tokens=2500).claims
    for claim in claims:  # ids the model invents do not count as support
        claim.evidence_ids = [i for i in claim.evidence_ids if i in known]
        if claim.status != "unsupported" and not claim.evidence_ids:
            claim.status = "unsupported"
            claim.reason = (claim.reason + " (no valid evidence id)").strip()
    return claims


def unsupported_count(claims: list[Claim]) -> int:
    return sum(1 for c in claims if c.status == "unsupported")


def verify_and_fix(draft: ProposalDraft, evidence: list[EvidenceItem]) -> ProposalDraft:
    """Verify the cover letter and screening answers; rewrite when anything is not fully supported."""
    with span("rag.verify_claims", kind="CHAIN", job_id=draft.job_id) as current:
        full_text = draft.cover_letter + "\n\n" + "\n".join(a.answer for a in draft.screening_answers)
        claims = verify_text(full_text, evidence)
        before = unsupported_count(claims)
        weak = [c for c in claims if c.status != "supported"]
        if weak:
            notes = "\n".join(f"- [{c.status}] {c.text} ({c.reason})" for c in weak)
            listing = _evidence_listing(evidence)
            draft.cover_letter = complete(
                "verifier", _rewrite_system(),
                f"<evidence>\n{listing}\n</evidence>\n\nClaims to fix:\n{notes}\n\n<proposal>\n"
                f"{draft.cover_letter}\n</proposal>").strip()
            for answer in draft.screening_answers:
                answer.answer = complete(
                    "verifier", _rewrite_system(),
                    f"<evidence>\n{listing}\n</evidence>\n\nClaims to fix:\n{notes}\n\n<proposal>\n"
                    f"{answer.answer}\n</proposal>").strip()
            full_text = draft.cover_letter + "\n\n" + "\n".join(a.answer for a in draft.screening_answers)
            claims = verify_text(full_text, evidence)
        draft.claims = claims
        draft.unsupported_before_verification = before
        draft.unsupported_after_verification = unsupported_count(claims)
        current.set_attribute("gigbid.unsupported_before", before)
        current.set_attribute("gigbid.unsupported_after", draft.unsupported_after_verification)
        return draft


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]
