"""Promotion rules: the only way knowledge enters long-term memory.

Style memory (namespace ("style", user)):
- Each approved edit is diffed against the draft. Deterministic detectors turn the diff into candidate rules:
  the opening sentence was cut, a word or short phrase was deleted, the letter was shortened a lot, a sign-off was
  removed.
- A candidate is stored in ("style_candidates", user) with a count. It is PROMOTED to style memory when it has been
  seen in at least `STYLE_MIN_EVIDENCE` separate edits (or the user pins it in Settings). One-off edits never become
  rules.

Outcome memory (namespace ("outcome", user)):
- Each marketplace outcome event (replied, interview, hired, declined, or no reply after 7 simulated days) is joined
  with the features GigBid itself recorded for that proposal (job category, opening type, evidence types used,
  price position). Raw tool output is never stored.
- A category's summary is PROMOTED (written or refreshed) only when it has at least `OUTCOME_MIN_PROPOSALS`
  resolved proposals, so one lucky reply does not steer the writer.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from collections import Counter
from typing import Any

STYLE_MIN_EVIDENCE = 2
OUTCOME_MIN_PROPOSALS = 3
POSITIVE = {"client_replied", "interview_requested", "hired"}

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")


def _first_sentence(text: str) -> str:
    return _SENTENCE.split(text.strip(), maxsplit=1)[0].strip() if text.strip() else ""


def _key(rule: str) -> str:
    return hashlib.sha1(rule.lower().encode()).hexdigest()[:12]


def style_candidates(draft: str, edited: str) -> list[dict[str, str]]:
    """Candidate style rules implied by one human edit (deterministic; no model involved)."""
    candidates: list[dict[str, str]] = []
    if not draft.strip() or not edited.strip() or draft.strip() == edited.strip():
        return candidates
    first = _first_sentence(draft)
    if first and first not in edited:
        candidates.append({"rule": "Cut the generic first sentence; open directly with the client's problem.",
                           "kind": "cut_opening", "example": first[:160]})
    draft_words = Counter(w.lower() for w in _WORD.findall(draft))
    edited_words = Counter(w.lower() for w in _WORD.findall(edited))
    matcher = difflib.SequenceMatcher(None, draft.split(), edited.split())
    for tag, i1, i2, _, _ in matcher.get_opcodes():
        if tag in ("delete", "replace") and 1 <= i2 - i1 <= 3:
            phrase = re.sub(r"[^\w\s'-]", "", " ".join(draft.split()[i1:i2])).strip().lower()
            words = phrase.split()
            if phrase and len(phrase) > 3 and all(edited_words[w] == 0 for w in words) and \
                    all(draft_words[w] <= 2 for w in words):
                candidates.append({"rule": f"Never use the phrase \"{phrase}\".", "kind": "banned_phrase",
                                   "example": phrase})
    draft_len, edited_len = len(draft.split()), len(edited.split())
    if draft_len and edited_len < 0.75 * draft_len:
        target = int(round(edited_len, -1))
        candidates.append({"rule": f"Keep cover letters short, about {target} words.", "kind": "shorter",
                           "example": f"{draft_len} -> {edited_len} words"})
    last = draft.strip().splitlines()[-1].strip() if draft.strip() else ""
    if last and len(last.split()) <= 6 and last not in edited:
        candidates.append({"rule": f"Do not end with a sign-off like \"{last[:40]}\".", "kind": "cut_signoff",
                           "example": last[:60]})
    unique: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        unique.setdefault(_key(candidate["rule"]), candidate)
    return [{"key": k, **v} for k, v in unique.items()]


def promote_style(store, user_id: str, draft: str, edited: str, thread_id: str) -> list[str]:
    """Record candidates from one edit; return the rules promoted by it."""
    promoted = []
    for candidate in style_candidates(draft, edited):
        namespace = ("style_candidates", user_id)
        item = store.get(namespace, candidate["key"])
        value = item.value if item else {"rule": candidate["rule"], "kind": candidate["kind"], "count": 0,
                                         "threads": [], "examples": []}
        if thread_id not in value["threads"]:
            value["count"] += 1
            value["threads"] = (value["threads"] + [thread_id])[-10:]
            value["examples"] = (value["examples"] + [candidate["example"]])[-5:]
        store.put(namespace, candidate["key"], value)
        if value["count"] >= STYLE_MIN_EVIDENCE and store.get(("style", user_id), candidate["key"]) is None:
            store.put(("style", user_id), candidate["key"],
                      {"rule": value["rule"], "kind": value["kind"], "evidence_count": value["count"],
                       "examples": value["examples"], "source": "promoted from edits"})
            promoted.append(value["rule"])
    return promoted


def pin_style_rule(store, user_id: str, rule: str) -> str:
    key = _key(rule)
    store.put(("style", user_id), key, {"rule": rule, "kind": "pinned", "evidence_count": 0, "examples": [],
                                        "source": "pinned by the user"})
    return key


def style_rules(store, user_id: str) -> list[str]:
    return [item.value["rule"] for item in store.search(("style", user_id), limit=50)]


def opening_type(cover_letter: str) -> str:
    first = _first_sentence(cover_letter).lower()
    if re.search(r"\b(dear|hello|hi|greetings)\b", first) or "perfect fit" in first or "i am a" in first:
        return "generic"
    if "?" in first:
        return "question"
    return "problem_first"


def proposal_features(category: str, cover_letter: str, evidence_types: list[str], amount: float,
                      p50: float | None) -> dict[str, Any]:
    position = "unknown" if not p50 else ("below_median" if amount < 0.9 * p50 else
                                          "above_median" if amount > 1.1 * p50 else "at_median")
    return {"category": category or "other", "opening": opening_type(cover_letter),
            "evidence_types": sorted(set(evidence_types)), "price_position": position,
            "words": len(cover_letter.split())}


def record_outcome(store, user_id: str, proposal_id: str, features: dict[str, Any], event_type: str) -> bool:
    """Add one resolved proposal to its category; promote the category summary when it has enough data."""
    category = features["category"]
    raw_ns = ("outcome_candidates", user_id)
    item = store.get(raw_ns, category)
    value = item.value if item else {"proposals": {}}
    value["proposals"][proposal_id] = {**features, "positive": event_type in POSITIVE, "event": event_type}
    store.put(raw_ns, category, value)
    resolved = list(value["proposals"].values())
    if len(resolved) < OUTCOME_MIN_PROPOSALS:
        return False
    positives = [p for p in resolved if p["positive"]]

    def rate(key: str, label: str) -> float | None:
        group = [p for p in resolved if p[key] == label]
        return round(sum(p["positive"] for p in group) / len(group), 3) if group else None

    summary = {
        "category": category, "n": len(resolved), "reply_rate": round(len(positives) / len(resolved), 3),
        "reply_rate_by_opening": {o: rate("opening", o) for o in ("problem_first", "question", "generic")},
        "reply_rate_by_price": {p: rate("price_position", p) for p in ("below_median", "at_median", "above_median")},
        "evidence_types_in_replies": Counter(t for p in positives for t in p["evidence_types"]).most_common(3),
        "median_words_in_replies": sorted(p["words"] for p in positives)[len(positives) // 2] if positives else None,
    }
    store.put(("outcome", user_id), category, summary)
    return True


def outcome_hint(store, user_id: str, category: str) -> str:
    item = store.get(("outcome", user_id), category or "other")
    if item is None:
        return ""
    s = item.value
    best_opening = max(((k, v) for k, v in s["reply_rate_by_opening"].items() if v is not None),
                       key=lambda kv: kv[1], default=(None, None))[0]
    parts = [f"In {s['category']} ({s['n']} past proposals, reply rate {s['reply_rate']:.0%})"]
    if best_opening:
        parts.append(f"'{best_opening}' openings got the most replies")
    if s.get("evidence_types_in_replies"):
        parts.append("replies came when citing " + ", ".join(t for t, _ in s["evidence_types_in_replies"]))
    if s.get("median_words_in_replies"):
        parts.append(f"about {s['median_words_in_replies']} words")
    return "; ".join(parts) + "."
