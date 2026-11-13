"""Evidence index per persona: dense vectors (pgvector, or an in-memory store for offline evaluation) and BM25.

- `VECTOR_STORE=pgvector` (default when DATABASE_URL is set) stores chunks and embeddings in Postgres/pgvector.
- `VECTOR_STORE=memory` keeps the same vectors in numpy; ranking is identical (exact cosine), used by tests and
  offline evaluation so they need no database.
- Re-indexing is incremental: a document is re-chunked and re-embedded only when its content hash changes.
"""
from __future__ import annotations

import json
import os
import pickle
import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from common.config import ROOT, load_config
from rag.index.embeddings import embed
from rag.ingest.chunker import Chunk, chunk_documents
from rag.ingest.loaders import Document, load_persona

PROCESSED = ROOT / "data" / "processed"
TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")


def tokenize(text: str) -> list[str]:
    """BM25 tokens: lower case, keeps names like c#, node.js, scikit-learn, dbt."""
    return [t.strip(".-") for t in TOKEN.findall(text.lower()) if len(t.strip(".-")) > 1]


@dataclass
class Hit:
    chunk: Chunk
    score: float


class EvidenceIndex:
    def __init__(self, persona: str, chunks: list[Chunk], vectors: np.ndarray, doc_hashes: dict[str, str]):
        self.persona = persona
        self.chunks = chunks
        self.vectors = vectors
        self.doc_hashes = doc_hashes
        self.by_id = {c.chunk_id: i for i, c in enumerate(chunks)}
        self.bm25 = BM25Okapi([tokenize(c.indexed_text) for c in chunks]) if chunks else None
        self._pg = _PgVectorStore() if _use_pgvector() else None

    # ------------------------------------------------------------------ search
    def dense(self, query: str, k: int, *, query_vector: np.ndarray | None = None,
              filters: dict | None = None) -> list[Hit]:
        vector = query_vector if query_vector is not None else embed([query], query=True)[0]
        if self._pg is not None:
            ids_scores = self._pg.search(self.persona, vector, k * 3 if filters else k)
            hits = [Hit(self.chunks[self.by_id[cid]], s) for cid, s in ids_scores if cid in self.by_id]
        else:
            scores = self.vectors @ vector
            order = np.argsort(-scores)
            hits = [Hit(self.chunks[i], float(scores[i])) for i in order[: k * 3 if filters else k]]
        return _apply_filters(hits, filters)[:k]

    def sparse(self, query: str, k: int, filters: dict | None = None) -> list[Hit]:
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        order = np.argsort(-scores)
        hits = [Hit(self.chunks[i], float(scores[i])) for i in order[: k * 3 if filters else k] if scores[i] > 0]
        return _apply_filters(hits, filters)[:k]

    # ------------------------------------------------------------------ persistence
    def save(self) -> None:
        folder = PROCESSED / self.persona
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / "vectors.npy", self.vectors)
        with open(folder / "chunks.pkl", "wb") as handle:
            pickle.dump(self.chunks, handle)
        (folder / "doc_hashes.json").write_text(json.dumps(self.doc_hashes), encoding="utf-8")
        if self._pg is not None:
            self._pg.replace(self.persona, self.chunks, self.vectors)

    @classmethod
    def load(cls, persona: str) -> EvidenceIndex | None:
        folder = PROCESSED / persona
        if not (folder / "chunks.pkl").exists():
            return None
        with open(folder / "chunks.pkl", "rb") as handle:
            chunks = pickle.load(handle)
        hashes = json.loads((folder / "doc_hashes.json").read_text(encoding="utf-8"))
        return cls(persona, chunks, np.load(folder / "vectors.npy"), hashes)


def _apply_filters(hits: list[Hit], filters: dict | None) -> list[Hit]:
    if not filters:
        return hits
    out = []
    for hit in hits:
        meta = hit.chunk.metadata
        if "types" in filters and meta.get("type") not in filters["types"]:
            continue
        if "outcome" in filters and meta.get("outcome") not in filters["outcome"]:
            continue
        if "skills" in filters and not set(s.lower() for s in filters["skills"]) & \
                set(s.lower() for s in meta.get("skills", [])):
            continue
        out.append(hit)
    return out


def build_index(persona: str, docs: list[Document] | None = None, *, contextualize=None,
                previous: EvidenceIndex | None = None) -> EvidenceIndex:
    """Build (or incrementally update) the index. `contextualize(chunk, doc)` adds V6 context lines."""
    config = load_config()["rag"]
    docs = docs if docs is not None else load_persona(persona)
    previous = previous if previous is not None else EvidenceIndex.load(persona)
    hashes = {d.evidence_id: d.content_hash for d in docs}
    keep_chunks: list[Chunk] = []
    keep_vectors: list[np.ndarray] = []
    changed = docs
    if previous is not None:
        unchanged = {e for e, h in hashes.items() if previous.doc_hashes.get(e) == h}
        for i, chunk in enumerate(previous.chunks):
            if chunk.evidence_id in unchanged:
                keep_chunks.append(chunk)
                keep_vectors.append(previous.vectors[i])
        changed = [d for d in docs if d.evidence_id not in unchanged]
    new_chunks = chunk_documents(changed, config["chunk_tokens"], config["chunk_overlap"])
    if contextualize is not None:
        doc_by_id = {d.evidence_id: d for d in changed}
        for chunk in new_chunks:
            chunk.context = contextualize(chunk, doc_by_id[chunk.evidence_id])
    new_vectors = embed([c.indexed_text for c in new_chunks]) if new_chunks else np.zeros((0, 1), np.float32)
    chunks = keep_chunks + new_chunks
    parts = ([np.stack(keep_vectors)] if keep_vectors else []) + ([new_vectors] if len(new_chunks) else [])
    vectors = np.concatenate(parts) if parts else np.zeros((0, load_config()["embeddings"]["dim"]), np.float32)
    index = EvidenceIndex(persona, chunks, vectors, hashes)
    index.reindexed_documents = len(changed)  # type: ignore[attr-defined]
    return index


# ---------------------------------------------------------------------------------------------------------
# pgvector backend
# ---------------------------------------------------------------------------------------------------------


def _use_pgvector() -> bool:
    mode = os.environ.get("VECTOR_STORE")
    if mode:
        return mode == "pgvector"
    return bool(os.environ.get("DATABASE_URL"))


class _PgVectorStore:
    def __init__(self) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self.conn = psycopg.connect(os.environ["DATABASE_URL"].replace("+psycopg", ""), autocommit=True)
        self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.conn)
        dim = load_config()["embeddings"]["dim"]
        self.conn.execute(f"""CREATE TABLE IF NOT EXISTS evidence_chunks (
            persona text NOT NULL, chunk_id text NOT NULL, evidence_id text NOT NULL, text text NOT NULL,
            metadata jsonb NOT NULL, embedding vector({dim}) NOT NULL, PRIMARY KEY (persona, chunk_id))""")

    def replace(self, persona: str, chunks: list[Chunk], vectors: np.ndarray) -> None:
        with self.conn.transaction():
            self.conn.execute("DELETE FROM evidence_chunks WHERE persona = %s", (persona,))
            with self.conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO evidence_chunks VALUES (%s, %s, %s, %s, %s, %s)",
                    [(persona, c.chunk_id, c.evidence_id, c.text, json.dumps(c.metadata), v)
                     for c, v in zip(chunks, vectors)])

    def search(self, persona: str, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            "SELECT chunk_id, 1 - (embedding <=> %s) AS score FROM evidence_chunks WHERE persona = %s "
            "ORDER BY embedding <=> %s LIMIT %s", (vector, persona, vector, k)).fetchall()
        return [(r[0], float(r[1])) for r in rows]
