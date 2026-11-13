# syntax=docker/dockerfile:1
# Marketplace MCP server (GigSim or live Upwork adapter)
FROM python:3.12.16-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app FASTEMBED_CACHE_PATH=/models
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.8
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml
COPY . .
RUN useradd --create-home --uid 10001 gigbid && mkdir -p /app/data/processed /app/data/audit /models \
    && chown -R gigbid /app/data /models
USER gigbid
EXPOSE 8102
CMD ["python", "-m", "mcp_servers.marketplace.server"]
