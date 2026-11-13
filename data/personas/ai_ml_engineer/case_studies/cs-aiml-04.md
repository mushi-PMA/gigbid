---
id: cs-aiml-04
project: Surface defect detection
date: 2023-07
industry: manufacturing
skills: [Computer Vision, Python]
---

# Case study: Surface defect detection

## Context

A mid-size company in the manufacturing sector came to me in 2023. They needed to spot scratches and dents on metal parts moving along a production line.

## What I did

- Frames are cropped, normalised and de-noised before the network sees them.
- I used Computer Vision for the central part of the solution.
- I used PyTorch for the central part of the solution.
- Python was the main tool here.
- Every model version is tracked, tested on a frozen set and promoted by a script.

## Result

Result: caught 96% of defects at under 80 ms per frame.

## Looking back

Weekly demos kept the client close to the work and removed surprises.
