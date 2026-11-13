---
id: cs-aiml-01
project: Invoice field extraction
date: 2025-08
industry: fintech
skills: [PyTorch, Python, FastAPI]
---

# Case study: Invoice field extraction

## Context

In 2025 a startup in fintech asked me to pull supplier, date, total and line items out of scanned supplier invoices without manual typing.

## What I did

- Most of the work was done with Python.
- The service ships as one image that runs the same on a laptop and in the cloud.
- Natural Language Processing did most of the heavy lifting.
- Most of the work was done with PyTorch.
- I built the core in FastAPI.
- Scanned pages were first turned into lines of text with positions before any model saw them.

## Result

After launch: cut manual review time by 38%.

## Looking back

Weekly demos kept the client close to the work and removed surprises.
