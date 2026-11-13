---
id: cs-aiml-12
project: Payment fraud scoring API
date: 2025-06
industry: payments
skills: [XGBoost, Python]
---

# Payment fraud scoring API

## Context

A startup in the payments sector came to me in 2025. They needed to score card payments for fraud in under 100 milliseconds before they are approved.

## What I did

Everything starts with a single compose command on any machine. Recent results are cached in memory so repeat requests return in milliseconds. XGBoost was the main tool here. I built the core in Python. I built the core in FastAPI.

## Result

What changed: caught 31% more fraud at the same false-positive rate.

## Looking back

Weekly demos kept the client close to the work and removed surprises.
