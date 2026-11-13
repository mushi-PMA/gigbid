"""Deterministic guards that run before and after the models: untrusted-text delimiting, pattern rules from the
policy pack (scam, injection, contact details, guarantees), and redaction. They never call a model."""
from __future__ import annotations

import re

from common.config import load_policy


def delimit(kind: str, text: str) -> str:
    """Wrap untrusted text in tags the prompts call data, and neutralise tag look-alikes inside it."""
    cleaned = re.sub(r"</?\s*(job_post|client_message|system|instructions?)\b[^>]*>", "[tag removed]", text or "",
                     flags=re.IGNORECASE)
    return f"<{kind}>\n{cleaned}\n</{kind}>"


def _patterns(section: str, key: str) -> list[re.Pattern]:
    return [re.compile(p) for p in load_policy().get(section, {}).get(key, [])]


def scam_signals(text: str) -> list[str]:
    return [m.group(0) for p in _patterns("risk", "scam_signals") for m in [p.search(text)] if m]


def injection_signals(text: str) -> list[str]:
    return [m.group(0) for p in _patterns("risk", "injection_signals") for m in [p.search(text)] if m]


def rule_patterns() -> dict[str, list[re.Pattern]]:
    return {rule["id"]: [re.compile(p) for p in rule.get("patterns", [])] for rule in load_policy()["rules"]}


def rule_actions() -> dict[str, str]:
    return {rule["id"]: rule.get("action", "rewrite") for rule in load_policy()["rules"]}


def find_violations(text: str) -> list[tuple[str, str]]:
    """(rule id, matched text) for every pattern rule the text breaks."""
    found = []
    for rule_id, patterns in rule_patterns().items():
        for pattern in patterns:
            for match in pattern.finditer(text or ""):
                found.append((rule_id, match.group(0)))
    return found


def redact(text: str) -> tuple[str, list[str]]:
    """Remove matches of rules whose action is `redact` (contact details, off-platform payment)."""
    actions = rule_actions()
    removed: list[str] = []
    for rule_id, patterns in rule_patterns().items():
        if actions.get(rule_id) != "redact":
            continue
        for pattern in patterns:
            removed += [m.group(0) for m in pattern.finditer(text)]
            text = pattern.sub("[removed]", text)
    return text, removed


def word_count(text: str) -> int:
    return len(re.sub(r"\[[^\]]+\]", "", text or "").split())
