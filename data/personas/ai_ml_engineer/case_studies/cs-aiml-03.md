---
id: cs-aiml-03
project: Grocery demand forecasting
date: 2024-07
industry: retail
skills: [Pandas, Time Series Analysis, XGBoost]
---

# Grocery demand forecasting

## Context

Brief (2024, retail): predict daily demand for fresh products in 40 stores so buyers stop over-ordering.

## What I did

- The team already knew Python, so I used it.
- I built the pipelines that land raw feeds into clean tables.
- The team already knew Time Series Analysis, so I used it.
- I used XGBoost for the central part of the solution.
- A nightly DAG pulls yesterday's data and rebuilds the tables.
- Pandas did most of the heavy lifting.

## Result

Outcome: reduced stock-outs by 22% and waste by 9%.

## Looking back

Weekly demos kept the client close to the work and removed surprises.
