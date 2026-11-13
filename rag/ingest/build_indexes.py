"""Build (or incrementally update) the evidence index of every persona.

    python -m rag.ingest.build_indexes                 # dense + BM25 for all personas
    python -m rag.ingest.build_indexes --contextual    # also the V6 index with generated context lines
"""
from __future__ import annotations

import argparse
import time

from rag.index.store import EvidenceIndex, build_index
from rag.ingest.loaders import list_personas, load_persona
from rag.variants.v6_contextual import contextualize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contextual", action="store_true", help="also build the V6 contextual index")
    parser.add_argument("--persona", action="append", help="only these personas")
    args = parser.parse_args()
    for persona in args.persona or list_personas():
        started = time.perf_counter()
        docs = load_persona(persona)
        index = build_index(persona, docs, previous=EvidenceIndex.load(persona))
        index.save()
        print(f"{persona}: {len(docs)} documents, {len(index.chunks)} chunks, re-embedded "
              f"{getattr(index, 'reindexed_documents', '?')} documents in {time.perf_counter() - started:.1f}s")
        if args.contextual:
            name = f"{persona}__ctx"
            ctx_index = build_index(name, docs, contextualize=contextualize, previous=EvidenceIndex.load(name))
            ctx_index.save()
            print(f"{name}: {len(ctx_index.chunks)} chunks")


if __name__ == "__main__":
    main()
