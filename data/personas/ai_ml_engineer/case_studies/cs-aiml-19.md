---
id: cs-aiml-19
project: Model serving platform
date: 2024-07
industry: consulting
skills: [Kubernetes, Amazon Web Services, MLOps]
---

# A model deployment platform for a enterprise in consulting

## Context

Brief (2024, consulting): give a data science team one repeatable way to ship models instead of ad hoc scripts.

## What I did

- The team already knew Kubernetes, so I used it.
- Most of the work was done with Docker.
- I built the core in Amazon Web Services.
- The glue and tooling are scripts in the language data teams use every day.
- Every merge runs the tests and builds a release automatically.
- MLOps did most of the heavy lifting.

## Result

What changed: cut model release time from two weeks to one day.

## Looking back

A small first release with real users taught us more than the planning did.
