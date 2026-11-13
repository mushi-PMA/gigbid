# homefinder

Listing site with map-based search and saved searches.

Stack: React, Django, PostgreSQL.

## What is in here

- `backend/propertys/views.py`
- `sql/v_property_kpis.sql`
- `src/components/PropertyList.tsx`

## Notes

- Built with React.
- Uses Django.
- Documented HTTP endpoints serve the front end.
- It works comfortably on small screens.
- Pull requests need a passing test run.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
