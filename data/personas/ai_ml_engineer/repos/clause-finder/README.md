# clause-finder

Answer questions over contract PDFs with cited clauses.

Stack: Retrieval-Augmented Generation, LangChain, OpenAI API, Python.

## What is in here

- `Dockerfile`
- `src/clause/api.py`
- `src/clause/search.py`

## Notes

- Stack: Retrieval-Augmented Generation.
- Uses LangChain.
- A nearest-neighbour lookup over stored passage embeddings finds candidate text.
- I wrote and versioned the instructions given to the language model and tested every wording change.
- Pull requests need a passing test run.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
