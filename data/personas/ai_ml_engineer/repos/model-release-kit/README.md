# model-release-kit

Scripts and notes from a client engagement. Work in progress, see the code for details.

## Files

- `.github/workflows/ci.yml`
- `Dockerfile`
- `deploy/model-serving.yaml`

## Run

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```
