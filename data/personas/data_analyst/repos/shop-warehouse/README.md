# shop-warehouse

Layered models with tests and a nightly refresh.

Stack: dbt, SQL, Data Warehousing.

## What is in here

- `dags/order_nightly.py`
- `models/marts/fct_orders.sql`
- `sql/v_order_kpis.sql`

## Notes

- Built with dbt.
- Implemented in SQL.
- I built the pipelines that land raw feeds into clean tables.
- Scheduled tasks with retries and dependencies run every night at 02:00.
- Config is read from environment variables.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
