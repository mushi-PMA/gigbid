"""`make eval`: every evaluation in order. Model calls are cached, so a rerun only pays for what changed.

Steps: retrieval variants -> ablation of the best -> decisions -> proposals (V0 and shipped) -> injection ->
tool granularity -> architectures -> model comparison -> X2 A/B -> holdout -> failure taxonomy -> tables.
Each step writes evals/results/<name>.json; scripts/make_tables.py turns them into the README and report tables.
"""
from __future__ import annotations

import os
import subprocess
import sys

STEPS = [
    ["evals.runners.rag_eval"],
    ["evals.runners.ablation", "--best", os.environ.get("RAG_BEST", "v2+v4")],
    ["evals.runners.decision_eval"],
    ["evals.runners.proposal_eval", "--name", "proposals_v0", "@RAG_VARIANT=v0"],
    ["evals.runners.proposal_eval", "--name", "proposals_best"],
    ["evals.runners.injection_eval"],
    ["evals.runners.tool_granularity"],
    ["evals.runners.architecture_comparison"],
    ["evals.runners.model_comparison"],
    ["evals.runners.x2_ab_test"],
    ["evals.runners.holdout_run"],
    ["evals.runners.failure_analysis"],
    ["scripts.make_tables"],
]


def main() -> None:
    only = set(sys.argv[1:])
    for step in STEPS:
        module, args = step[0], [a for a in step[1:] if not a.startswith("@")]
        if only and module.split(".")[-1] not in only:
            continue
        env = dict(os.environ)
        for item in step[1:]:
            if item.startswith("@"):
                key, value = item[1:].split("=", 1)
                env[key] = value
        print(f"\n=== {module} {' '.join(args)}", flush=True)
        subprocess.run([sys.executable, "-m", module, *args], check=True, env=env)


if __name__ == "__main__":
    main()
