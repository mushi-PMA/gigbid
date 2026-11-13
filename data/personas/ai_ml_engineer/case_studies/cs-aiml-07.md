---
id: cs-aiml-07
project: Call transcripts and summaries
date: 2024-06
industry: healthcare
skills: [Speech Recognition, Python]
---

# A call transcription and summary pipeline for a mid-size company in healthcare

## Context

In 2024 a mid-size company in healthcare asked me to turn recorded patient calls into text and a short note that nurses can check in seconds.

## What I did

- I used Python for the central part of the solution.
- A general-purpose language model writes the first version and rules check it.
- I built the core in Speech Recognition.
- I built the core in Hugging Face.
- Storage is S3 and compute is EC2 behind a load balancer.

## Result

What changed: saved agents about four minutes per call.

## Looking back

Handover notes and a recorded walkthrough made the last week calm.
