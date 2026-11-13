# Failure analysis

Failed dev jobs are collected by `python -m evals.runners.failure_analysis` into `evals/results/failures.json`
(categories: missed evidence, wrong skip, wrong bid, mispriced, unsupported claim, generic opening, compliance miss,
injection, tool error). Each group was then read by hand; the table below records the cause, the fix tried and
whether it worked, with the metric before and after the fix.

## Counts by category (dev set)

<!-- results:failures -->
_Not measured yet: run `make eval` (needs a model key)._
<!-- /results:failures -->

## Hand analysis (at least 10 failed jobs)

| # | Job id | Persona | Category | Root cause (what the trace shows) | Fix tried | Worked? (before, after) |
|---|--------|---------|----------|-----------------------------------|-----------|-------------------------|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| 7 | | | | | | |
| 8 | | | | | | |
| 9 | | | | | | |
| 10 | | | | | | |

## Patterns

To be written after the dev evaluation: which categories share a cause, and which fixes moved a metric.
