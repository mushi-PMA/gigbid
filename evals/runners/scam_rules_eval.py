"""Scam pattern rules alone (no model) on every dev and holdout job: how many gold scams they catch and how many
ordinary jobs they flag. The rules were written from the dev failures; the holdout scams come from the same kinds of
post, so the holdout numbers are an upper bound for unseen scam types.

    python -m evals.runners.scam_rules_eval
"""
from __future__ import annotations

import json

from agent.nodes.guards import scam_signals
from evals.runners.common import PERSONAS, load_set, write_result


def evaluate(split: str) -> dict:
    caught = missed = flagged = ordinary = 0
    for persona in PERSONAS:
        for item in load_set(persona, split):
            job = item["job"]
            hit = bool(scam_signals(f"{job['title']}\n{job['description']}"))
            if item["gold"].get("scam"):
                caught, missed = caught + hit, missed + (not hit)
            else:
                flagged, ordinary = flagged + hit, ordinary + 1
    return {"scams": caught + missed, "scams_caught": caught, "recall": round(caught / max(1, caught + missed), 4),
            "ordinary_jobs": ordinary, "ordinary_flagged": flagged,
            "false_positive_rate": round(flagged / max(1, ordinary), 4)}


def main() -> None:
    result = {split: evaluate(split) for split in ("dev", "holdout")}
    print(json.dumps(result, indent=1))
    write_result("scam_rules", result)


if __name__ == "__main__":
    main()
