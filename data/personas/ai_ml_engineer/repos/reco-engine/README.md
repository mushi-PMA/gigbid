# reco-engine

Train a two-tower retrieval model and serve top-k items.

Stack: Recommendation Systems, Python, PyTorch.

## What is in here

- `analysis/interaction_test.py`
- `src/interaction/train.py`

## Notes

- Built with Recommendation Systems.
- Built with Python.
- Users were split at random and the difference was read with confidence intervals.
- Hot lookups are served from an in-memory key-value store with expiry.
- Config is read from environment variables.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
