"""Ablation of the best retrieval pipeline: remove one component at a time, report by persona and job type.

    python -m evals.runners.ablation --best v1+v2+v3+v5
"""
from __future__ import annotations

import argparse

from evals.runners.common import PERSONAS, enable_cache, write_result
from evals.runners.rag_eval import evaluate
from rag.retriever import parse_variant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--best", required=True, help="the best variant combination, e.g. v1+v2+v3+v5")
    parser.add_argument("--personas", nargs="*", default=PERSONAS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    enable_cache("rag")
    parts = sorted(parse_variant(args.best))
    runs = {"full": args.best}
    for part in parts:
        rest = [p for p in parts if p != part]
        runs[f"without {part}"] = "+".join(rest) if rest else "v0"
    results = {}
    for label, variant in runs.items():
        result = evaluate(variant, args.personas, args.limit)
        print(f"{label:>14} ({variant}): R@5 {result['overall']['recall@5']:.3f} nDCG@10 "
              f"{result['overall']['ndcg@10']:.3f}")
        results[label] = {k: v for k, v in result.items() if k != "rows"}
    write_result("ablation", {"best": args.best, "results": results})


if __name__ == "__main__":
    main()
