"""V6 contextual retrieval: a generated context line is prepended to each chunk before embedding and BM25.

The line says which project, document and skill area the chunk belongs to, so fragments ("the nightly job retries
twice") keep their meaning out of context. Lines are generated once at index time and cached.
"""
from __future__ import annotations

from agent.prompts import load_prompt
from common.llm import complete
from rag.ingest.chunker import Chunk
from rag.ingest.loaders import Document

NAME = "v6"
GROUP = "indexing"


def contextualize(chunk: Chunk, doc: Document) -> str:
    user = (f"<document title=\"{doc.title}\" type=\"{doc.type}\">\n{doc.text[:3000]}\n</document>\n"
            f"<chunk>\n{chunk.text[:1200]}\n</chunk>\nWrite the context sentence for this chunk.")
    return complete("rag_helper", load_prompt("rag_context"), user, max_tokens=120).strip().splitlines()[0][:300]
