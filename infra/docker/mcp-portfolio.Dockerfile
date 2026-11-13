# syntax=docker/dockerfile:1
# Portfolio MCP server (read-only, Streamable HTTP)
FROM python:3.12.16-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app FASTEMBED_CACHE_PATH=/models
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.8
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml
# open embedding and reranker models are baked into the image (CPU, ONNX)
COPY agent/config.yaml agent/config.yaml
COPY common/__init__.py common/config.py common/
COPY rag/__init__.py rag/
COPY rag/index/__init__.py rag/index/embeddings.py rag/index/
RUN python -c "from rag.index.embeddings import embed, rerank_scores; embed(['warm up']); rerank_scores('a', ['b'])"
COPY . .
RUN useradd --create-home --uid 10001 gigbid && mkdir -p /app/data/processed /app/data/audit /models \
    && chown -R gigbid /app/data /models
USER gigbid
EXPOSE 8101
CMD ["python", "-m", "mcp_servers.portfolio.server"]
