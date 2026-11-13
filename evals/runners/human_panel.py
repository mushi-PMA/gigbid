"""Blind pairwise human panel: classmates compare anonymised proposals (baseline V0 against the shipped pipeline) for
the same job, without knowing which is which.

1. export:  python -m evals.runners.human_panel export   -> evals/datasets/human_panel.csv
            Each row shows one job and two proposals as "Proposal 1" and "Proposal 2" (order randomised and recorded
            in a separate key file). Raters write 1 or 2 in `preferred` (or 0 for no preference) and their initials.
2. score:   python -m evals.runners.human_panel score    -> evals/results/human_panel.json
            win rate of the shipped pipeline and an exact binomial test against 50%.
"""
from __future__ import annotations

import csv
import json
import random
import sys

from scipy.stats import binomtest

from common.config import ROOT
from evals.runners.common import RESULTS, write_result

SHEET = ROOT / "evals" / "datasets" / "human_panel.csv"
KEY = ROOT / "evals" / "datasets" / "human_panel_key.json"


def _texts(name: str) -> dict[str, dict]:
    path = RESULTS / f"{name}_texts.jsonl"
    return {row["job_id"]: row for row in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if row}


def export(baseline: str = "proposals_v0", shipped: str = "proposals_best") -> None:
    base, best = _texts(baseline), _texts(shipped)
    rng = random.Random(7)
    key = {}
    with open(SHEET, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair", "job_title", "proposal_1", "proposal_2", "preferred", "rater"])
        for number, job_id in enumerate(sorted(set(base) & set(best)), start=1):
            shipped_first = rng.random() < 0.5
            first, second = (best[job_id], base[job_id]) if shipped_first else (base[job_id], best[job_id])
            key[str(number)] = 1 if shipped_first else 2
            writer.writerow([number, best[job_id]["title"], first["cover_letter"], second["cover_letter"], "", ""])
    KEY.write_text(json.dumps(key), encoding="utf-8")
    print(f"wrote {SHEET} ({len(key)} pairs); keep {KEY.name} away from raters")


def score() -> None:
    key = json.loads(KEY.read_text(encoding="utf-8"))
    rows = [r for r in csv.DictReader(open(SHEET, encoding="utf-8")) if r["preferred"].strip() in ("0", "1", "2")]
    wins = sum(1 for r in rows if int(r["preferred"]) == key[r["pair"]])
    ties = sum(1 for r in rows if r["preferred"] == "0")
    decided = len(rows) - ties
    write_result("human_panel", {
        "judgements": len(rows), "raters": len({r["rater"] for r in rows}), "shipped_wins": wins,
        "baseline_wins": decided - wins, "ties": ties,
        "shipped_win_rate": round(wins / decided, 4) if decided else None,
        "binomial_p": round(binomtest(wins, decided, 0.5).pvalue, 4) if decided else None})


if __name__ == "__main__":
    {"export": export, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "export"]()
