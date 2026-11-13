"""30-job smoke evaluation for CI, with failure thresholds (evals/thresholds.yaml).

Runs 10 dev jobs per persona through decisions and retrieval, and 2 per persona through full proposals. Model calls
replay from the committed cache in evals/smoke_cache, so pull requests need no API key; a cache miss without a key
fails the job with a clear message. Fails (exit 1) if bid-or-skip F1 drops or unsupported claims rise past the
thresholds.

    python -m evals.runners.smoke_eval
"""
from __future__ import annotations

import asyncio
import os
import sys

import yaml

from common.config import ROOT
from evals.runners import decision_eval, proposal_eval, rag_eval
from evals.runners.common import PERSONAS, write_result

THRESHOLDS = ROOT / "evals" / "thresholds.yaml"


def main() -> None:
    os.environ.setdefault("GIGBID_LLM_CACHE", str(ROOT / "evals" / "smoke_cache"))
    limits = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))
    decisions = asyncio.run(decision_eval.evaluate(PERSONAS, 10, "dev"))
    retrieval = rag_eval.evaluate(_shipped(), PERSONAS, 10)
    proposals, _ = asyncio.run(proposal_eval.evaluate(PERSONAS, 2, "dev"))
    measured = {"bid_or_skip_f1": decisions["bid_or_skip"]["f1"],
                "scam_recall": decisions["scam_detection"]["recall"],
                "evidence_recall_at_5": retrieval["overall"]["recall@5"],
                "unsupported_claims_per_proposal":
                    proposals["unsupported_claims_per_proposal"]["after_verification"] or 0.0}
    failures = []
    for key, value in measured.items():
        rule = limits[key]
        if "min" in rule and value < rule["min"]:
            failures.append(f"{key} {value} < {rule['min']}")
        if "max" in rule and value > rule["max"]:
            failures.append(f"{key} {value} > {rule['max']}")
    write_result("smoke", {"measured": measured, "thresholds": limits, "failures": failures})
    if failures:
        print("SMOKE EVAL FAILED:\n- " + "\n- ".join(failures))
        sys.exit(1)
    print("smoke eval passed", measured)


def _shipped() -> str:
    from common.config import load_config

    return load_config()["rag"]["variant"]


if __name__ == "__main__":
    main()
