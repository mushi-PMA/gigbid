"""Shared evaluation pieces: datasets, project-level gold, metrics, the offline marketplace, result files.

Every number in the README and the report comes from a JSON file in evals/results/ written by these runners. Each
file records the git commit, the config, the model profile and the time, so it can be traced and regenerated.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common.config import ROOT, load_config

DATASETS = ROOT / "evals" / "datasets"
RESULTS = ROOT / "evals" / "results"
PERSONAS = ["ai_ml_engineer", "fullstack_web_dev", "data_analyst"]


async def run_parallel(items: list[Any], worker: Any) -> list[Any]:
    """`await worker(item)` for every item, at most EVAL_PARALLEL (default 1) at a time; results keep input order.
    Jobs share nothing but the read-only marketplace, so order does not change any result except latency, which
    then includes waiting for rate-limited endpoints (reported with the parallelism used)."""
    import asyncio

    gate = asyncio.Semaphore(int(os.environ.get("EVAL_PARALLEL", "1")))

    async def one(item: Any) -> Any:
        async with gate:
            return await worker(item)

    return list(await asyncio.gather(*(one(item) for item in items)))


def enable_cache(name: str = "eval") -> None:
    """Cache model calls so reruns are free and repeatable (folder is git-ignored except the smoke cache)."""
    os.environ.setdefault("GIGBID_LLM_CACHE", str(ROOT / "evals" / "cache" / name))


def load_set(persona: str, split: str = "dev") -> list[dict[str, Any]]:
    return json.loads((DATASETS / f"{split}_{persona}.json").read_text(encoding="utf-8"))


def project_of(persona: str) -> dict[str, str]:
    """evidence id prefix -> project id, from the persona's structured project list (gold side only)."""
    projects = json.loads((ROOT / "data" / "personas" / persona / "projects.json").read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for project in projects:
        for artifact in project.get("artifacts", []):
            kind, name = artifact.split(":", 1)
            prefix = {"case_study": "cs", "repo": "readme", "proposal": "proposal"}.get(kind, kind)
            mapping[f"{persona}:{prefix}:{name}"] = project["project_id"]
            if kind == "repo":
                mapping[f"{persona}:code:{name}/"] = project["project_id"]
    return mapping


def to_project(evidence_id: str, mapping: dict[str, str], fallback: str = "") -> str:
    if evidence_id in mapping:
        return mapping[evidence_id]
    for prefix, project in mapping.items():
        if prefix.endswith("/") and evidence_id.startswith(prefix):
            return project
    return fallback


def ranked_projects(items: Iterable[Any], mapping: dict[str, str]) -> list[str]:
    """Retrieved evidence -> ranked unique projects (an evidence item is a project described in any form)."""
    out: list[str] = []
    for item in items:
        project = to_project(item.evidence_id, mapping, item.project)
        if project and project not in out:
            out.append(project)
    return out


def retrieval_metrics(ranked: list[str], gold: set[str]) -> dict[str, float]:
    """Recall@5, MRR and nDCG@10 over ranked unique items against the gold set."""
    if not gold:
        return {}
    hits5 = sum(1 for p in ranked[:5] if p in gold)
    rr = next((1.0 / (i + 1) for i, p in enumerate(ranked) if p in gold), 0.0)
    dcg = sum(1.0 / math.log2(i + 2) for i, p in enumerate(ranked[:10]) if p in gold)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), 10)))
    return {"recall@5": hits5 / len(gold), "recall@5_capped": hits5 / min(len(gold), 5), "mrr": rr,
            "ndcg@10": dcg / ideal if ideal else 0.0}


def mean_by(rows: list[dict[str, Any]], key: str, metrics: list[str]) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    return {g: {m: round(sum(r[m] for r in rs if m in r) / max(1, sum(1 for r in rs if m in r)), 4) for m in metrics}
            | {"n": len(rs)} for g, rs in sorted(groups.items())}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return round(values[low] + (values[high] - values[low]) * (position - low), 4)


def f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


def job_text(job: dict[str, Any]) -> str:
    return f"{job['title']}\n{job['description']}"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def write_result(name: str, payload: dict[str, Any]) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    config = load_config()
    meta = {"generated_at": datetime.now(UTC).isoformat(), "commit": git_commit(),
            "model_profile": config["models"]["profile"], "rag_variant": config["rag"]["variant"],
            "embedding_model": config["embeddings"]["model"], "reranker": config["embeddings"]["reranker"]}
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps({"meta": meta, **payload}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")
    return path


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.start
