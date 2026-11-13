---
id: cs-data-11
project: Warehouse for an online shop
date: 2024-05
industry: e-commerce
skills: [dbt, SQL]
---

# Warehouse for an online shop

## Context

The client, a startup working in e-commerce, wanted to pull orders, ads and support data into one trusted set of tables.

## What I did

- Extract, reshape and load steps feed the reporting tables each night.
- dbt did most of the heavy lifting.
- The team already knew SQL, so I used it.
- Most of the work was done with Data Warehousing.
- I built the pipelines that land raw feeds into clean tables.
- Scheduled tasks with retries and dependencies run every night at 02:00.

## Result

Outcome: gave the team one revenue number everyone agreed on.

## Looking back

Handover notes and a recorded walkthrough made the last week calm.
