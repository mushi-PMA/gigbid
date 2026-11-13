# syntax=docker/dockerfile:1
# GigSim marketplace simulator (REST API on port 8081)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app GIGSIM_PORT=8081 GIGSIM_DB=/data/gigsim.db
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.8
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml
# the app, the model client for the optional LLM judge, and the seed data
COPY gigsim gigsim
COPY common common
COPY agent/config.yaml agent/config.yaml
COPY data/gigsim data/gigsim
COPY data/personas data/personas
RUN useradd --create-home --uid 10001 gigsim && mkdir -p /data && chown -R gigsim /data
USER gigsim
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health')"
CMD ["python", "-m", "gigsim.server"]
