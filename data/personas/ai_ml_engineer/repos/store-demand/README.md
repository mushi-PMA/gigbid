# store-demand

Forecast units sold per store and product for the next 14 days.

Stack: Python, Time Series Analysis, XGBoost, Pandas.

## What is in here

- `dags/sales_nightly.py`
- `src/sales/features.py`

## Notes

- Python for the main logic.
- Uses Time Series Analysis.
- A nightly DAG pulls yesterday's data and rebuilds the tables.
- The nightly loads and the tables other teams query were part of the job.
- Config is read from environment variables.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
