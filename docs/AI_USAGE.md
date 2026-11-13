# AI usage

As the assignment allows, AI coding and writing assistants were used during this project.

- **Tools used:** a coding assistant in the editor and terminal.
- **Files assisted:** scaffolding and first drafts across the repository (Python services, React screens, tests,
  Docker files and documentation). Every file was read, run and revised, and every number in the README and the
  report comes from the evaluation scripts and the files in `evals/results/`.
- **One issue caught:** the assistant ran an automatic lint fix over the whole repository, which also rewrote files
  under `gigsim/` and the persona sample code. Those must never change (GigSim is the simulator everything is graded
  against, and the corpora are the evaluation data). The checksum test in `scripts/check_rules.py` caught it; the
  files were restored from git, and `gigsim/`, `data/personas/` and `tests/fixtures/` were excluded from linting in
  `pyproject.toml` so it cannot happen again.
