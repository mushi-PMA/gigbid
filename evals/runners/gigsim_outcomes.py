"""GigSim outcomes per proposal study (layout from the brief): reply and hire rates from the committed proposal
results. The outcomes themselves are produced when each study submits its drafts to GigSim's simulated clients
(`harness.EvalMarketplace.submit_proposal`, used by `proposal_eval`, `x2_ab_test` and `holdout_run`).

    python -m evals.runners.gigsim_outcomes
"""
from __future__ import annotations

import json

from evals.runners.common import RESULTS


def main() -> None:
    for path in sorted(RESULTS.glob("proposals_*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        print(f"{path.stem:32} proposals {result['n_proposals']:>3}  reply rate {result['gigsim_reply_rate']}  "
              f"hire rate {result['gigsim_hire_rate']}")


if __name__ == "__main__":
    main()
