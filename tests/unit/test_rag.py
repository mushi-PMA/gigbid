"""Retrieval on a tiny fixture corpus (open embedding model on CPU), fusion, chunking and claim verification."""
from __future__ import annotations

import json

from agent.handoffs import EvidenceItem, ProposalDraft
from rag.index.store import Hit, build_index, tokenize
from rag.ingest.chunker import Chunk, chunk_document
from rag.ingest.loaders import Document, load_persona
from rag.variants.base import rrf


def test_loader_reads_every_source_with_metadata(fixture_personas):
    docs = load_persona("test_dev")
    types = {d.type for d in docs}
    assert {"case_study", "readme", "code", "review", "proposal"} <= types
    proposal = next(d for d in docs if d.evidence_id == "test_dev:proposal:prop-1")
    assert proposal.outcome == "won" and proposal.project == "p1"
    readme = next(d for d in docs if d.evidence_id == "test_dev:readme:etl-kit")
    assert readme.project == "p1" and readme.client_industry == "retail"


def test_bm25_tokens_keep_tool_names():
    assert {"node.js", "c#", "scikit-learn", "dbt"} <= set(tokenize("Node.js, C#, scikit-learn and dbt models"))


def test_code_chunks_keep_functions_together():
    doc = Document("x:code:r/a.py", "x", "code", "def a():\n    return 1\n\n\ndef b():\n    return 2\n")
    chunks = chunk_document(doc, size=200)
    assert len(chunks) == 1 and "def b" in chunks[0].text


def test_rrf_prefers_items_ranked_high_in_both_lists():
    chunk = lambda i: Chunk(f"d{i}#0", f"d{i}", "t", {})  # noqa: E731
    fused = rrf([[Hit(chunk(1), 1), Hit(chunk(2), 1)], [Hit(chunk(2), 1), Hit(chunk(3), 1)]])
    assert fused[0].chunk.chunk_id == "d2#0"


def test_variants_find_the_right_project(fixture_personas):
    from rag.retriever import Retriever

    for variant in ("v0", "v2", "v2+v3", "v2+v4+v5"):
        items = Retriever("test_dev", variant, k=3).search_text("Airflow DAG nightly data loads")
        assert items[0].project == "p1", variant


def test_outcome_boost_demotes_ignored_proposals(fixture_personas):
    from rag.retriever import Retriever

    plain = Retriever("test_dev", "v2", k=8).search_text("React developer proposal")
    boosted = Retriever("test_dev", "v2+v4", k=8).search_text("React developer proposal")
    rank = lambda items: [i.evidence_id for i in items].index("test_dev:proposal:prop-2")  # noqa: E731
    assert rank(boosted) >= rank(plain)


def test_incremental_reindex_only_embeds_changed_documents(fixture_personas):
    first = build_index("test_dev")
    first.save()
    (fixture_personas / "test_dev" / "case_studies" / "cs-3.md").write_text(
        "---\nid: cs-3\ntitle: New work\n---\nA dbt model for finance reporting.\n", encoding="utf-8")
    second = build_index("test_dev", previous=first)
    assert second.reindexed_documents == 1
    assert len(second.chunks) == len(first.chunks) + 1


def test_claim_verification_removes_unsupported_claims(scripted_llm):
    from rag.verify import verify_and_fix

    evidence = [EvidenceItem(evidence_id="p:cs:1", persona="p", type="case_study", text="Built an Airflow DAG.")]
    first = {"claims": [{"text": "I built an Airflow DAG", "evidence_ids": ["p:cs:1"], "status": "supported"},
                        {"text": "I led a team of 20", "evidence_ids": [], "status": "unsupported"}]}
    second = {"claims": [{"text": "I built an Airflow DAG", "evidence_ids": ["p:cs:1"], "status": "supported"}]}
    scripted_llm({"verifier": [json.dumps(first), "I built an Airflow DAG [p:cs:1].", json.dumps(second)]})
    draft = verify_and_fix(ProposalDraft(job_id="j", cover_letter="I built an Airflow DAG [p:cs:1]. I led a team of 20."),
                           evidence)
    assert draft.unsupported_before_verification == 1 and draft.unsupported_after_verification == 0
    assert "team of 20" not in draft.cover_letter


def test_invented_evidence_ids_do_not_count(scripted_llm):
    from rag.verify import verify_text

    scripted_llm({"verifier": {"claims": [{"text": "x", "evidence_ids": ["made:up"], "status": "supported"}]}})
    claims = verify_text("x", [EvidenceItem(evidence_id="real", persona="p", type="cv", text="t")])
    assert claims[0].status == "unsupported"
