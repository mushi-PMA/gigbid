# fraud-score-api

Low-latency fraud model behind a scoring endpoint.

Stack: XGBoost, FastAPI, Python.

## What is in here

- `.github/workflows/ci.yml`
- `Dockerfile`
- `src/payment/api.py`
- `src/payment/pipeline.py`

## Notes

- Stack: XGBoost.
- Stack: FastAPI.
- Deployments use a pinned build recipe so library versions never drift.
- Recent results are cached in memory so repeat requests return in milliseconds.
- See the case study for the business background.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
