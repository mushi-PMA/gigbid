"""Signature extension X2: two proposal strategies as an A/B test in GigSim, with a significance test on reply rate.

A (writer): open with the client's problem, then the most relevant evidence.
B (writer_strategy_b): open with a credentials summary, then a numbered plan.
Both arms write for the SAME jobs (paired design), so the test is an exact McNemar test on the discordant pairs
(jobs where only one arm got a reply); a two-proportion z-test is reported too.

    python -m evals.runners.x2_ab_test --per-persona 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os

from scipy.stats import binomtest, norm

from common.config import load_config
from evals.runners import proposal_eval
from evals.runners.common import PERSONAS, RESULTS, enable_cache, write_result

ARMS = {"A": "writer", "B": "writer_strategy_b"}


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> float:
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2)) if 0 < pooled < 1 else 0
    return 2 * (1 - norm.cdf(abs(x1 / n1 - x2 / n2) / se)) if se else 1.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-persona", type=int, default=20)
    args = parser.parse_args()
    enable_cache("x2")
    replies: dict[str, dict[str, bool]] = {}
    summaries = {}

    async def run_arms() -> None:
        # both arms in one event loop: the in-process MCP sessions opened for the first arm belong to its loop, so a
        # second asyncio.run would make every job of the second arm fail before any model call
        for arm, strategy in ARMS.items():
            os.environ["WRITER_STRATEGY"] = strategy
            load_config.cache_clear()
            summary, proposals = await proposal_eval.evaluate(PERSONAS, args.per_persona, "dev")
            if arm == "B":  # arm A writes the same letters as proposals_best; B's join the judge calibration pool
                with open(RESULTS / "proposals_x2_B_texts.jsonl", "w", encoding="utf-8") as handle:
                    handle.writelines(json.dumps(p) + "\n" for p in proposals)
            summaries[arm] = {**{k: v for k, v in summary.items() if k != "rows"},
                              "jobs": [{k: r.get(k) for k in ("job_id", "status", "drafted", "replied")}
                                       for r in summary["rows"]]}
            replies[arm] = {r["job_id"]: bool(r.get("replied")) for r in summary["rows"] if "replied" in r}

    asyncio.run(run_arms())
    os.environ.pop("WRITER_STRATEGY", None)
    load_config.cache_clear()
    common = sorted(set(replies["A"]) & set(replies["B"]))
    only_a = sum(1 for j in common if replies["A"][j] and not replies["B"][j])
    only_b = sum(1 for j in common if replies["B"][j] and not replies["A"][j])
    a_hits, b_hits = sum(replies["A"][j] for j in common), sum(replies["B"][j] for j in common)
    mcnemar = binomtest(only_a, only_a + only_b, 0.5).pvalue if only_a + only_b else 1.0
    result = {"paired_jobs": len(common), "reply_rate_A": round(a_hits / len(common), 4) if common else None,
              "reply_rate_B": round(b_hits / len(common), 4) if common else None, "only_A_replied": only_a,
              "only_B_replied": only_b, "mcnemar_exact_p": round(mcnemar, 4),
              "two_proportion_z_p": round(two_proportion_z(a_hits, len(common), b_hits, len(common)), 4)
              if common else None, "significant_at_0_05": mcnemar < 0.05, "arms": summaries}
    print({k: v for k, v in result.items() if k != "arms"})
    write_result("x2_ab_test", result)


if __name__ == "__main__":
    main()
