"""Change request (platform policy v2, 2 November 2026): checks that GigBid follows GigSim's new rule and cost
using only the updated policy pack."""
from __future__ import annotations

from datetime import UTC, datetime

from agent.handoffs import Job
from agent.nodes.guards import redact
from agent.nodes.pricing import connects_cost
from common.config import load_policy
from gigsim import policy as gigsim_policy

V2_TIME = datetime(2026, 11, 5, tzinfo=UTC)


def test_connects_cost_matches_gigsim_v2():
    policy = load_policy()
    assert policy["version"] == "v2"
    for payment_type, budget in (("fixed", 1500), ("fixed", 999), ("hourly", 60), ("hourly", 40)):
        job = Job(job_id="j", title="t", description="d", payment_type=payment_type, budget_max=budget,
                  connects_cost=8)
        assert connects_cost(job, policy) == gigsim_policy.connects_cost(job.model_dump(), V2_TIME)


def test_links_are_removed_before_approval():
    cleaned, removed = redact("See my demo at https://example.dev/demo and www.portfolio.example for details.")
    assert "http" not in cleaned and "www." not in cleaned and len(removed) == 2
    assert gigsim_policy.violations(cleaned, [], V2_TIME) == []  # GigSim would now accept the proposal
