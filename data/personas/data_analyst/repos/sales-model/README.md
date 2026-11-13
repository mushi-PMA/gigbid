# sales-model

Star-schema model and report pages for weekly sales.

Stack: Microsoft Power BI, SQL, Microsoft Excel.

## What is in here

- `model/measures.dax`
- `sql/v_sale_kpis.sql`

## Notes

- Relies on Microsoft Power BI.
- Stack: SQL.
- A shared model holds the definitions once, so every report agrees.
- A governed reporting layer serves the whole business with agreed definitions.
- Sample data is synthetic.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
