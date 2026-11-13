# retention-cohorts

Cohort retention tables and curves.

Stack: SQL, Python, Looker Studio.

## What is in here

- `models/marts/fct_subscriptions.sql`
- `sql/subscription_retention.sql`

## Notes

- Relies on SQL.
- Python for the main logic.
- A central analytics store sits apart from the live application database.
- Fact and dimension tables are arranged in a star layout with agreed definitions.
- Config is read from environment variables.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
