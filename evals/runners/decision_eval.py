"""Decisions on the dev set (or the holdout set): bid-or-skip F1, scam and injection detection, price inside the fair
band, latency, tokens and USD per job analysed. The graph stops before the Writer, so no proposal is drafted.

    python -m evals.runners.decision_eval --limit 60
"""

from __future__ import annotations

import argparse
import asyncio
import json

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.graphs.bid_graph import compile_bid_graph
from evals.runners.common import PERSONAS, enable_cache, f1, load_set, mean_by, percentile, write_result
from evals.runners.harness import EvalMarketplace, install, run_job


async def evaluate(personas: list[str], limit: int | None, split: str) -> dict:
    rows = []
    for persona in personas:
        items = load_set(persona, split)[:limit]
        market = EvalMarketplace([i["job"] for i in items])
        install(market, persona)
        graph = compile_bid_graph(InMemorySaver(), InMemoryStore(), interrupt_before=["writer"])
        for item in items:
            job, gold = item["job"], item["gold"]
            result = await run_job(job, persona, graph=graph)
            state = result["state"]
            decision = state.get("decision")
            risk = state.get("risk")
            price = state.get("price")
            band = gold.get("fair_price") or {}
            in_band = None
            if price is not None and band.get("low") is not None:
                in_band = band["low"] <= price.amount <= band["high"]
            rows.append(
                {
                    "persona": persona,
                    "job_id": job["job_id"],
                    "kind": job.get("kind", "regular"),
                    "job_type": gold.get("job_type", "other"),
                    "gold_bid": bool(gold.get("bid")),
                    "pred_bid": bool(decision and decision.action == "bid"),
                    "pred_action": decision.action if decision else state.get("status"),
                    "gold_scam": bool(gold.get("scam")),
                    "pred_scam": bool(risk and risk.is_scam),
                    "gold_injection": bool(gold.get("injection")),
                    "pred_injection": bool(risk and risk.injection_detected),
                    "price_in_band": in_band,
                    "fit": state["fit"].score if state.get("fit") else None,
                    "status": state.get("status"),
                    "status_reason": state.get("status_reason", ""),
                    "seconds": result["analysed_seconds"],
                    "tokens": result["tokens"],
                    "usd": result["usd"],
                }
            )
    return summarise(rows)


def summarise(rows: list[dict]) -> dict:
    def confusion(gold_key: str, pred_key: str, subset=None) -> dict:
        subset = subset if subset is not None else rows
        tp = sum(1 for r in subset if r[gold_key] and r[pred_key])
        fp = sum(1 for r in subset if not r[gold_key] and r[pred_key])
        fn = sum(1 for r in subset if r[gold_key] and not r[pred_key])
        return f1(tp, fp, fn)

    priced = [r for r in rows if r["price_in_band"] is not None and r["gold_bid"]]
    by_persona = {
        p: {
            "bid": confusion("gold_bid", "pred_bid", [r for r in rows if r["persona"] == p]),
            "scam": confusion("gold_scam", "pred_scam", [r for r in rows if r["persona"] == p]),
        }
        for p in sorted({r["persona"] for r in rows})
    }
    for row in rows:
        row["correct"] = float(row["gold_bid"] == row["pred_bid"])
    return {
        "n": len(rows),
        "bid_or_skip": confusion("gold_bid", "pred_bid"),
        "bid_accuracy": round(sum(r["correct"] for r in rows) / max(1, len(rows)), 4),
        "scam_detection": confusion("gold_scam", "pred_scam"),
        "injection_detection": confusion("gold_injection", "pred_injection"),
        "price_inside_fair_band": round(sum(r["price_in_band"] for r in priced) / len(priced), 4) if priced else None,
        "priced_jobs": len(priced),
        "per_job_analysed": {
            "p50_seconds": percentile([r["seconds"] for r in rows], 0.5),
            "p95_seconds": percentile([r["seconds"] for r in rows], 0.95),
            "mean_tokens": round(sum(r["tokens"] for r in rows) / max(1, len(rows))),
            "mean_usd": round(sum(r["usd"] for r in rows) / max(1, len(rows)), 6),
        },
        "by_persona": by_persona,
        "by_job_type": mean_by(rows, "job_type", ["correct"]),
        "errors": [r for r in rows if r["status"] in ("dead_letter", "needs_attention")],
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--personas", nargs="*", default=PERSONAS)
    parser.add_argument("--limit", type=int, default=None, help="jobs per persona")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--name", default="decisions")
    args = parser.parse_args()
    enable_cache("decisions")
    summary = asyncio.run(evaluate(args.personas, args.limit, args.split))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "errors")}, indent=1)[:3000])
    write_result(args.name, {"split": args.split, "limit_per_persona": args.limit, **summary})


if __name__ == "__main__":
    main()
