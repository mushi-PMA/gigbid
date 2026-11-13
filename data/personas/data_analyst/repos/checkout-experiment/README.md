# checkout-experiment

Experiment readout with power, uplift and guard metrics.

Stack: Python, Statistics, SQL.

## What is in here

- `analysis/visit_test.py`
- `sql/visit_retention.sql`

## Notes

- Stack: Python.
- Stack: Statistics.
- New versions ran against the old one on a random half of traffic before full rollout.
- Weekly charts show the trend by topic and location.
- See the case study for the business background.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
