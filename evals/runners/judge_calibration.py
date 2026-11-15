"""Judge calibration: compare the LLM judge with the freelancer's own labels on 30 proposals (Cohen's kappa).

1. export:  python -m evals.runners.judge_calibration export   -> evals/datasets/judge_labels.csv (30 proposals,
            no judge scores in it; they go to judge_labels_key.json). Fill the `human_overall` column (1 to 5)
            yourself, reading each proposal against its job, without opening the key file.
2. score:   python -m evals.runners.judge_calibration score    -> evals/results/judge_calibration.json
            (Cohen's kappa, quadratic-weighted kappa, exact and within-one agreement, and the disagreements).
"""
from __future__ import annotations

import csv
import json
import random
import sys

from common.config import ROOT
from evals.runners.common import RESULTS, write_result

LABELS = ROOT / "evals" / "datasets" / "judge_labels.csv"
KEY = ROOT / "evals" / "datasets" / "judge_labels_key.json"


def kappa(a: list[int], b: list[int], weighted: bool = False) -> float:
    categories = [1, 2, 3, 4, 5]
    n = len(a)
    observed = [[0] * 5 for _ in categories]
    for x, y in zip(a, b):
        observed[x - 1][y - 1] += 1
    row = [sum(observed[i]) for i in range(5)]
    col = [sum(observed[i][j] for i in range(5)) for j in range(5)]
    weight = (lambda i, j: (i - j) ** 2 / 16) if weighted else (lambda i, j: 0.0 if i == j else 1.0)
    po = sum(weight(i, j) * observed[i][j] for i in range(5) for j in range(5)) / n
    pe = sum(weight(i, j) * row[i] * col[j] for i in range(5) for j in range(5)) / n / n
    return round(1 - po / pe, 4) if pe else 1.0


def export() -> None:
    texts = []
    for path in sorted(RESULTS.glob("proposals_*_texts.jsonl")):
        texts += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    random.Random(2026).shuffle(texts)
    jobs = {}
    for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        for item in json.loads((ROOT / "evals" / "datasets" / f"dev_{persona}.json").read_text(encoding="utf-8")):
            jobs[item["job"]["job_id"]] = item["job"]
    with open(LABELS, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item", "job_id", "job_title", "job_post", "proposal", "human_overall"])
        for number, text in enumerate(texts[:30], start=1):
            job = jobs.get(text["job_id"], {})
            writer.writerow([number, text["job_id"], text["title"], job.get("description", "")[:1500],
                             text["cover_letter"], ""])
    KEY.write_text(json.dumps({str(n): t["judge"]["overall"] for n, t in enumerate(texts[:30], start=1)}),
                   encoding="utf-8")
    print(f"wrote {LABELS} ({min(30, len(texts))} proposals); fill human_overall (1-5), then run `score`")


def score() -> None:
    rows = [r for r in csv.DictReader(open(LABELS, encoding="utf-8")) if r["human_overall"].strip()]
    if len(rows) < 30:
        sys.exit(f"only {len(rows)} labelled items; label all 30 first")
    human = [int(r["human_overall"]) for r in rows]
    key = json.loads(KEY.read_text(encoding="utf-8"))
    model = [int(key[r["item"]]) for r in rows]
    disagreements = [{"item": r["item"], "job_id": r["job_id"], "human": h, "judge": m}
                     for r, h, m in zip(rows, human, model) if abs(h - m) >= 2]
    write_result("judge_calibration", {
        "n": len(rows), "cohen_kappa": kappa(human, model), "quadratic_weighted_kappa": kappa(human, model, True),
        "exact_agreement": round(sum(h == m for h, m in zip(human, model)) / len(rows), 4),
        "within_one": round(sum(abs(h - m) <= 1 for h, m in zip(human, model)) / len(rows), 4),
        "mean_human": round(sum(human) / len(human), 3), "mean_judge": round(sum(model) / len(model), 3),
        "disagreements": disagreements})


if __name__ == "__main__":
    {"export": export, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "export"]()
