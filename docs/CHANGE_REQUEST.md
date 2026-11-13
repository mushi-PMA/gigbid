# Change request: platform policy v2 (2 November 2026)

## What changed
GigSim's policy update, in force from 2 November 2026 (`GET /v1/policy` returns `v2` from then on):
1. **New cost:** premium jobs (fixed budget of $1,000 or more, or hourly rate of $50 or more) cost 4 extra Connects.
2. **New rule `no_external_links`:** cover letters and screening answers must not contain URLs; GigSim rejects such
   submissions with HTTP 422.

## What we had to edit
Only the policy pack, because rules, patterns and Connects pricing live in configuration
(`data/policy_pack/policy.yaml`), read at run time by the Pricing Strategist (`connects_cost`) and the Compliance
Guard (`redact`, `find_violations`).

Commit `Change request: platform policy v2 ...`:

| File | Change |
|---|---|
| `data/policy_pack/policy.yaml` | version v2; two `connects.surcharges` entries; rule `no_external_links` with one URL pattern (action `redact`) |
| `data/policy_pack/marketplace_policy.md` | one new numbered rule in the plain-text summary |
| `tests/unit/test_policy_v2.py` | new test: our Connects cost equals GigSim's v2 cost; links are removed before approval and GigSim then accepts the text |

Policy files: **13 lines added, 4 removed. Python code changed: 0 lines.** Show it with `git show --stat HEAD~N`
(the change-request commit) or `git log --oneline -- data/policy_pack`.

## How long it took
About 15 minutes from reading GigSim's v2 policy to a passing test: reading the new rules, adding two surcharge rows
and one rule with a pattern, and writing the test.

## What it says about the design
Keeping rules, patterns, prices and thresholds in configuration made the change a data edit: no node, prompt or
graph change, so no regression risk in the agents. Two things still needed thought: the surcharge had to be
expressible with our `min_budget` and `payment_type` fields (it was), and the right action for links was `redact`
(remove before the human sees the draft), not `block`, because a link is easy to drop and the rest of the proposal
is still good. A rule that needed new logic (for example "no more than 3 proposals per client per week") would need
code in the Pricing Strategist; the pattern-and-surcharge format would not cover it.
