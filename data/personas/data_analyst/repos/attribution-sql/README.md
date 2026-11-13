# attribution-sql

Channel attribution queries and a report.

Stack: Google Analytics, SQL, Looker Studio.

## What is in here

- `sql/session_retention.sql`
- `sql/v_session_kpis.sql`

## Notes

- Stack: Google Analytics.
- Implemented in SQL.
- Ad spend was joined with orders to see return per channel.
- Inconsistent records were tidied first, with a log of every change.
- Tests live next to the code they cover.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
