# call-notes

Transcribe call audio and generate a structured summary.

Stack: Speech Recognition, Python, Hugging Face.

## What is in here

- `src/call/api.py`
- `src/call/infer.py`

## Notes

- Uses Speech Recognition.
- Built with Python.
- A general-purpose language model writes the first version and rules check it.
- Storage is S3 and compute is EC2 behind a load balancer.
- Config is read from environment variables.

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
