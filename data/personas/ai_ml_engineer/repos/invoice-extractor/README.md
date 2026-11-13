# invoice-extractor

Turn scanned invoice images into structured JSON fields.

Stack: Python, Natural Language Processing, PyTorch, FastAPI.

## What is in here

- `Dockerfile`
- `src/invoice/api.py`
- `src/invoice/train.py`

## Notes

- Implemented in Python.
- Natural Language Processing for the main logic.
- Pages that arrive as pictures go through a text-recognition step first.
- Everything starts with a single compose command on any machine.
- Tests live next to the code they cover.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
