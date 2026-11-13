# prompt-regression

Regression test suite for prompts and model versions.

Stack: Large Language Models, Python, Prompt Engineering.

## What is in here

- `.github/workflows/ci.yml`
- `src/evalcase/run_eval.py`

## Notes

- Uses Large Language Models.
- Python for the main logic.
- A pipeline checks and deploys each commit.
- Proper sampling and hypothesis tests replaced eyeballing charts.
- See the case study for the business background.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
