---
id: cs-web-19
project: Support chat widget
date: 2024-02
industry: saas
skills: [Node.js, Redis]
---

# A live chat widget for a scale-up in saas

## Context

A scale-up in the saas sector came to me in 2024. They needed to add a chat bubble to customer sites that agents answer from one inbox.

## What I did

Everything starts with a single compose command on any machine. A JSON API that both web and mobile clients call, with documented endpoints. I picked Node.js because it kept the code short and testable. I picked React because it kept the code short and testable. I used Redis for the central part of the solution.

## Result

After launch: answered first messages within 40 seconds on average.

## Looking back

Most of the delay came from waiting for access, so I now ask for it in week one.
