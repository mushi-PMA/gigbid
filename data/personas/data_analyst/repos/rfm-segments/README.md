# rfm-segments

Recency, frequency and value segments with profiles.

Stack: Python, Pandas, Tableau.

## What is in here

- `etl/clean_orders.py`
- `src/order/segments.py`

## Notes

- Relies on Python.
- Relies on Pandas.
- Effects were checked with confidence intervals and significance tests.
- Inconsistent records were tidied first, with a log of every change.
- Config is read from environment variables.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
