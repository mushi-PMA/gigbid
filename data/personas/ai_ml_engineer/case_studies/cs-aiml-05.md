---
id: cs-aiml-05
project: Contract clause search
date: 2025-05
industry: legal tech
skills: [OpenAI API, LangChain, Retrieval-Augmented Generation]
---

# Contract clause search

## Context

Brief (2025, legal tech): let lawyers ask plain questions about a pile of contracts and get the exact clause back.

## What I did

- The team already knew OpenAI API, so I used it.
- I picked Retrieval-Augmented Generation because it kept the code short and testable.
- The model sits behind async Python endpoints with request validation.
- I picked Python because it kept the code short and testable.
- I wrote and versioned the instructions given to the language model and tested every wording change.
- I picked LangChain because it kept the code short and testable.
- A nearest-neighbour lookup over stored passage embeddings finds candidate text.

## Result

After launch: cut clause lookup from 15 minutes to under 20 seconds.

## Looking back

A small first release with real users taught us more than the planning did.
