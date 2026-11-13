"""R&D question B: retrieval quality of every RAG variant on the dev set, per persona, job type and requirement count.

An evidence item is a portfolio project: its case study, README, code and past proposals describe the same work, so
a variant is scored on the ranked list of unique projects it returns (gold = projects behind the job's relevant
evidence). Also reports doc-level nDCG@10 for reference.

    python -m evals.runners.rag_eval        # variants that need no model, plus the rest when a key works
    python -m evals.runners.rag_eval --variants v0 v1+v2+v3 --limit 60
"""
from __future__ import annotations

import argparse
import time

from evals.runners.common import (
    PERSONAS,
    enable_cache,
    job_text,
    load_set,
    mean_by,
    percentile,
    project_of,
    ranked_projects,
    retrieval_metrics,
    write_result,
)
from rag.retriever import Retriever, parse_variant

OFFLINE_VARIANTS = ["v0", "v2", "v0+v3", "v2+v3", "v2+v4", "v2+v5", "v2+v3+v4", "v2+v3+v5", "v2+v3+v4+v5"]
MODEL_VARIANTS = ["v1", "v1+v2", "v1+v2+v3", "v1+v2+v3+v5", "v7", "v2+v3+v7", "v6+v2+v3", "v1+v2+v3+v8"]
NEEDS_MODEL = {"v1", "v6", "v7", "v8"}
METRICS = ["recall@5", "recall@5_capped", "mrr", "ndcg@10", "seconds"]


def evaluate(variant: str, personas: list[str], limit: int | None, split: str = "dev") -> dict:
    rows = []
    for persona in personas:
        mapping = project_of(persona)
        retriever = Retriever(persona, variant, k=10)
        items = [i for i in load_set(persona, split) if i["gold"].get("relevant_evidence")]
        for item in items[:limit]:
            gold = {p for p in (mapping.get(e) or _code_project(e, mapping) for e in item["gold"]["relevant_evidence"])
                    if p}
            started = time.perf_counter()
            result = retriever.retrieve(job_text(item["job"]), None, k=10)
            seconds = time.perf_counter() - started
            metrics = retrieval_metrics(ranked_projects(result.items, mapping), gold)
            requirements = item["gold"].get("requirements_count", 0)
            rows.append({"persona": persona, "job_id": item["job"]["job_id"],
                         "job_type": item["gold"].get("job_type", "other"),
                         "requirements": "4+" if requirements >= 4 else "1-3", "seconds": seconds, **metrics})
    overall = {m: round(sum(r[m] for r in rows) / len(rows), 4) for m in METRICS} if rows else {}
    overall["p95_seconds"] = percentile([r["seconds"] for r in rows], 0.95)
    return {"variant": variant, "n": len(rows), "overall": overall,
            "by_persona": mean_by(rows, "persona", METRICS), "by_job_type": mean_by(rows, "job_type", METRICS),
            "by_requirements": mean_by(rows, "requirements", METRICS), "rows": rows}


def _code_project(evidence_id: str, mapping: dict[str, str]) -> str | None:
    for prefix, project in mapping.items():
        if prefix.endswith("/") and evidence_id.startswith(prefix):
            return project
    return None


def model_available() -> bool:
    from common.llm import LLMError, complete

    try:
        complete("rag_helper", "Reply with OK.", "OK?", max_tokens=20)
        return True
    except LLMError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="*")
    parser.add_argument("--personas", nargs="*", default=PERSONAS)
    parser.add_argument("--limit", type=int, default=None, help="jobs per persona")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--name", default="rag_variants")
    args = parser.parse_args()
    enable_cache("rag")
    variants = args.variants or OFFLINE_VARIANTS + MODEL_VARIANTS
    has_model = None
    results, skipped = [], []
    for variant in variants:
        if parse_variant(variant) & NEEDS_MODEL:
            has_model = model_available() if has_model is None else has_model
            if not has_model:
                skipped.append(variant)
                continue
        result = evaluate(variant, args.personas, args.limit, args.split)
        print(f"{variant:>16}  R@5 {result['overall']['recall@5']:.3f}  MRR {result['overall']['mrr']:.3f}  "
              f"nDCG@10 {result['overall']['ndcg@10']:.3f}  n={result['n']}")
        results.append(result)
    write_result(args.name, {"split": args.split, "limit_per_persona": args.limit, "results": results,
                             "skipped_need_model": skipped})


if __name__ == "__main__":
    main()
