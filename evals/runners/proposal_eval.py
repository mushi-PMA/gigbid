"""Proposals end to end on a fixed set of dev jobs whose gold label is bid: unsupported claims before and after claim
verification, judge score, GigSim reply and hire rate, latency, tokens and USD per proposal.

    RAG_VARIANT=v0 python -m evals.runners.proposal_eval --name proposals_v0
    python -m evals.runners.proposal_eval --name proposals_best            # shipped variant from config
"""
from __future__ import annotations

import argparse
import asyncio
import json

from evals.runners.common import PERSONAS, RESULTS, enable_cache, load_set, percentile, write_result
from evals.runners.harness import EvalMarketplace, install, run_job
from evals.runners.judge import judge


def fixed_jobs(persona: str, per_persona: int, split: str = "dev") -> list[dict]:
    """The same jobs for every configuration: gold bids that are not scams, injections or duplicates."""
    items = [i for i in load_set(persona, split) if i["gold"].get("bid") and i["job"].get("kind", "regular") ==
             "regular"]
    return items[:per_persona]


async def evaluate(personas: list[str], per_persona: int, split: str = "dev") -> tuple[dict, list[dict]]:
    rows, proposals = [], []
    for persona in personas:
        items = fixed_jobs(persona, per_persona, split)
        market = EvalMarketplace([i["job"] for i in items])
        install(market, persona)
        for item in items:
            job = item["job"]
            result = await run_job(job, persona, approve=True)
            state = result["state"]
            draft = state.get("draft")
            row = {"persona": persona, "job_id": job["job_id"], "job_type": item["gold"].get("job_type", "other"),
                   "drafted": result["drafted"], "status": state.get("status"), "seconds": result["seconds"],
                   "tokens": result["tokens"], "usd": result["usd"],
                   "revisions": state.get("revision", 0)}
            if draft is not None and result["drafted"]:
                score = await asyncio.to_thread(judge, job, draft.cover_letter)
                outcome = market.outcomes.get(job["job_id"], {})
                row.update(unsupported_before=draft.unsupported_before_verification,
                           unsupported_after=draft.unsupported_after_verification, claims=len(draft.claims),
                           judge_overall=score.overall, judge=score.model_dump(), replied=bool(outcome.get("replied")),
                           hired=bool(outcome.get("hired")), interview=bool(outcome.get("interview")))
                proposals.append({"persona": persona, "job_id": job["job_id"], "title": job["title"],
                                  "cover_letter": draft.cover_letter, "judge": score.model_dump(),
                                  "claims": [c.model_dump() for c in draft.claims]})
            rows.append(row)
    return summarise(rows), proposals


def summarise(rows: list[dict]) -> dict:
    done = [r for r in rows if "judge_overall" in r]
    mean = lambda key: round(sum(r[key] for r in done) / len(done), 4) if done else None  # noqa: E731
    return {"n_jobs": len(rows), "n_proposals": len(done),
            "unsupported_claims_per_proposal": {"before_verification": mean("unsupported_before"),
                                                "after_verification": mean("unsupported_after")},
            "unsupported_claim_rate": {
                "before": round(sum(r["unsupported_before"] for r in done) / max(1, sum(r["claims"] for r in done)), 4),
                "after": round(sum(r["unsupported_after"] for r in done) / max(1, sum(r["claims"] for r in done)), 4)},
            "judge_overall": mean("judge_overall"), "gigsim_reply_rate": mean("replied"),
            "gigsim_hire_rate": mean("hired"), "mean_revisions": mean("revisions"),
            "per_proposal": {"p50_seconds": percentile([r["seconds"] for r in done], 0.5),
                             "p95_seconds": percentile([r["seconds"] for r in done], 0.95),
                             "mean_tokens": round(sum(r["tokens"] for r in done) / max(1, len(done))),
                             "mean_usd": round(sum(r["usd"] for r in done) / max(1, len(done)), 6)},
            "by_persona": {p: {"reply_rate": round(sum(r["replied"] for r in done if r["persona"] == p) /
                                                   max(1, sum(1 for r in done if r["persona"] == p)), 4),
                               "judge": round(sum(r["judge_overall"] for r in done if r["persona"] == p) /
                                              max(1, sum(1 for r in done if r["persona"] == p)), 3)}
                           for p in sorted({r["persona"] for r in done})},
            "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--personas", nargs="*", default=PERSONAS)
    parser.add_argument("--per-persona", type=int, default=12)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--name", default="proposals_best")
    args = parser.parse_args()
    enable_cache("proposals")
    summary, proposals = asyncio.run(evaluate(args.personas, args.per_persona, args.split))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))
    write_result(args.name, {"split": args.split, "per_persona": args.per_persona, **summary})
    with open(RESULTS / f"{args.name}_texts.jsonl", "w", encoding="utf-8") as handle:
        for proposal in proposals:
            handle.write(json.dumps(proposal) + "\n")


if __name__ == "__main__":
    main()
