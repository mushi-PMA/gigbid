"""Held-out test run against the declared budgets (R8, E5).

The holdout sets (50 jobs per persona, disjoint from the dev set and never used for tuning) stand in for the hidden
test set: every job is analysed, every bid is drafted and approved unchanged (simulated human), and latency, cost and
quality are compared with the budgets declared in agent/config.yaml before this run.

    python -m evals.runners.holdout_run                          # all 50 jobs per persona
    python -m evals.runners.holdout_run --decisions 10 --proposals 2   # free-tier sizes (docs/HYPOTHESES.md)
"""
from __future__ import annotations

import argparse
import asyncio

from common.config import load_config
from evals.runners import decision_eval, proposal_eval
from evals.runners.common import PERSONAS, enable_cache, write_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=int, default=None, help="holdout jobs per persona (default: all)")
    parser.add_argument("--proposals", type=int, default=50, help="bid jobs per persona drafted end to end")
    args = parser.parse_args()
    enable_cache("holdout")
    declared = load_config()["budgets"]["declared"]
    decisions = asyncio.run(decision_eval.evaluate(PERSONAS, args.decisions, "holdout"))
    proposals, _ = asyncio.run(proposal_eval.evaluate(PERSONAS, args.proposals, "holdout"))
    measured = {"p95_latency_seconds_per_job_analysed": decisions["per_job_analysed"]["p95_seconds"],
                "p95_latency_seconds_per_proposal": proposals["per_proposal"]["p95_seconds"],
                "usd_per_job_analysed": decisions["per_job_analysed"]["mean_usd"],
                "usd_per_proposal": proposals["per_proposal"]["mean_usd"]}
    verdicts = {k: (measured[k] is not None and measured[k] <= declared[k]) for k in declared}
    write_result("holdout", {"declared": declared, "measured": measured, "within_budget": verdicts,
                             "decision_jobs_per_persona": args.decisions, "proposal_jobs_per_persona": args.proposals,
                             "decisions": {k: v for k, v in decisions.items() if k not in ("rows",)},
                             "proposals": {k: v for k, v in proposals.items() if k != "rows"}})
    for key in declared:
        print(f"{key}: declared {declared[key]}, measured {measured[key]} -> {'met' if verdicts[key] else 'MISSED'}")


if __name__ == "__main__":
    main()
