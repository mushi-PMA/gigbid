"""Open embedding and reranking models on CPU (fastembed, ONNX). Models are set in agent/config.yaml."""
from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

from common.config import load_config


def _threads() -> int | None:
    """CPU threads for the ONNX models (env EMBED_THREADS); default: all cores."""
    value = os.environ.get("EMBED_THREADS")
    return int(value) if value else None


@lru_cache(maxsize=2)
def _embedder(name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=name, threads=_threads())


@lru_cache(maxsize=2)
def _cross_encoder(name: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=name, threads=_threads())


def embed(texts: list[str], *, query: bool = False) -> np.ndarray:
    """L2-normalised embeddings, shape (n, dim). bge models use a query prefix for queries."""
    name = load_config()["embeddings"]["model"]
    if "nomic" in name.lower():
        texts = [f"{'search_query' if query else 'search_document'}: {t}" for t in texts]
    elif query and "bge" in name.lower():
        texts = [f"Represent this sentence for searching relevant passages: {t}" for t in texts]
    vectors = np.array(list(_embedder(name).embed(texts, batch_size=32)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    name = load_config()["embeddings"]["reranker"]
    return [float(s) for s in _cross_encoder(name).rerank(query, passages, batch_size=16)]
