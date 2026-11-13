"""Collect failed dev jobs from the decision and proposal results into the report's failure taxonomy.

Categories: missed evidence, wrong skip, wrong bid, mispriced, unsupported claim, generic opening, compliance miss,
injection, tool error. Writes evals/results/failures.json with every failed job and its evidence, for the hand
analysis (cause, fix tried, whether it worked) in docs/FAILURES.md.

    python -m evals.runners.failure_analysis
"""
from __future__ import annotations

import json

from agent.memory.promotion_rules import opening_type
from agent.nodes.guards import find_violations
from evals.runners.common import RESULTS, write_result


def load(name: str) -> dict:
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    failures = []
    decisions = load("decisions")
    for row in decisions.get("rows", []):
        if row["status"] in ("dead_letter", "needs_attention"):
            failures.append({**row, "category": "tool error"})
        elif row["gold_injection"] and row["pred_bid"]:
            failures.append({**row, "category": "injection"})
        elif row["gold_bid"] and not row["pred_bid"]:
            failures.append({**row, "category": "missed evidence" if (row["fit"] or 0) < 0.4 else "wrong skip"})
        elif row["pred_bid"] and not row["gold_bid"]:
            failures.append({**row, "category": "wrong bid"})
        elif row["price_in_band"] is False:
            failures.append({**row, "category": "mispriced"})
    texts = []
    for path in RESULTS.glob("proposals_best_texts.jsonl"):
        texts += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for text in texts:
        if any(c["status"] == "unsupported" for c in text["claims"]):
            failures.append({"job_id": text["job_id"], "persona": text["persona"], "category": "unsupported claim",
                             "claims": [c for c in text["claims"] if c["status"] == "unsupported"]})
        if opening_type(text["cover_letter"]) == "generic":
            failures.append({"job_id": text["job_id"], "persona": text["persona"], "category": "generic opening",
                             "opening": text["cover_letter"][:160]})
        violations = find_violations(text["cover_letter"])
        if violations:
            failures.append({"job_id": text["job_id"], "persona": text["persona"], "category": "compliance miss",
                             "violations": violations})
    counts: dict[str, int] = {}
    for failure in failures:
        counts[failure["category"]] = counts.get(failure["category"], 0) + 1
    write_result("failures", {"counts": counts, "failures": failures})
    print(counts)


if __name__ == "__main__":
    main()
