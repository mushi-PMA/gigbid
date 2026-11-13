---
id: cs-aiml-02
project: Support ticket triage
date: 2024-01
industry: saas
skills: [scikit-learn, Natural Language Processing]
---

# A support-ticket routing model for a scale-up in saas

## Context

A scale-up in the saas sector came to me in 2024. They needed to send each incoming support ticket to the right team and flag the urgent ones.

## What I did

- I used Python for the central part of the solution.
- A monitoring job compares live inputs with the training data and alerts on drift.
- Natural Language Processing did most of the heavy lifting.
- New versions ran against the old one on a random half of traffic before full rollout.
- scikit-learn did most of the heavy lifting.

## Result

Result: lifted first-contact routing accuracy from 71% to 93%.

## Looking back

I kept a short decision log, which saved a long meeting when priorities changed.
