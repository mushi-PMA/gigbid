"""Split documents into overlapping chunks. Code is split on blank lines first so functions stay together."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag.ingest.loaders import Document


@dataclass
class Chunk:
    chunk_id: str             # <evidence_id>#<n>
    evidence_id: str
    text: str
    metadata: dict = field(default_factory=dict)
    context: str = ""         # V6 contextual line, prepended for embedding and BM25 when present

    @property
    def indexed_text(self) -> str:
        header = f"{self.metadata.get('title', '')}\n"
        return f"{self.context}\n{header}{self.text}" if self.context else f"{header}{self.text}"


def _windows(words: list[str], size: int, overlap: int) -> list[list[str]]:
    if len(words) <= size:
        return [words]
    step = max(1, size - overlap)
    return [words[i:i + size] for i in range(0, max(1, len(words) - overlap), step)]


def chunk_document(doc: Document, size: int = 220, overlap: int = 40) -> list[Chunk]:
    if doc.type == "code":
        blocks = [b for b in re.split(r"\n\s*\n", doc.text) if b.strip()]
        pieces: list[str] = []
        current: list[str] = []
        for block in blocks:
            if current and len(" ".join(current + [block]).split()) > size:
                pieces.append("\n\n".join(current))
                current = []
            current.append(block)
        if current:
            pieces.append("\n\n".join(current))
    else:
        pieces = [" ".join(w) for w in _windows(doc.text.split(), size, overlap)]
    meta = doc.metadata()
    return [Chunk(f"{doc.evidence_id}#{n}", doc.evidence_id, piece, meta) for n, piece in enumerate(pieces)
            if piece.strip()]


def chunk_documents(docs: list[Document], size: int = 220, overlap: int = 40) -> list[Chunk]:
    return [chunk for doc in docs for chunk in chunk_document(doc, size, overlap)]
