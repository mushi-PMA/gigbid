"""Choose models by measurement: two open configurations on the same dev jobs (quality, latency, cost).

    open      = gpt-oss-20b for frequent nodes, gpt-oss-120b for Writer and Critic (routing by node)
    open_qwen = Qwen3-32B for every node
The judge and the simulated clients use the same model in both runs, so scores are comparable.

    python -m evals.runners.model_comparison --decisions 30 --proposals 6
"""
from __future__ import annotations

import argparse
import asyncio
import os

from common.config import load_config
from evals.runners import decision_eval, proposal_eval
from evals.runners.common import PERSONAS, enable_cache, write_result

PROFILES = ["open", "open_qwen"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=int, default=30, help="dev jobs per persona for decisions")
    parser.add_argument("--proposals", type=int, default=6, help="bid jobs per persona for proposals")
    args = parser.parse_args()
    enable_cache("models")
    results = {}
    for profile in PROFILES:
        os.environ["MODEL_PROFILE"] = profile
        load_config.cache_clear()
        decisions = asyncio.run(decision_eval.evaluate(PERSONAS, args.decisions, "dev"))
        proposals, _ = asyncio.run(proposal_eval.evaluate(PERSONAS, args.proposals, "dev"))
        results[profile] = {
            "bid_or_skip_f1": decisions["bid_or_skip"]["f1"], "scam_recall": decisions["scam_detection"]["recall"],
            "price_inside_fair_band": decisions["price_inside_fair_band"],
            "per_job_analysed": decisions["per_job_analysed"], "judge_overall": proposals["judge_overall"],
            "unsupported_after": proposals["unsupported_claims_per_proposal"]["after_verification"],
            "gigsim_reply_rate": proposals["gigsim_reply_rate"], "per_proposal": proposals["per_proposal"],
            "hardware": "hosted (Amazon Bedrock on-demand); no local GPU"}
        print(profile, results[profile])
    os.environ.pop("MODEL_PROFILE", None)
    load_config.cache_clear()
    write_result("model_comparison", {"decision_jobs_per_persona": args.decisions,
                                      "proposal_jobs_per_persona": args.proposals, "results": results})


if __name__ == "__main__":
    main()
