"""Claim verifier node (layout from the brief). The node is defined next to the Writer in `writer.py`, because it
checks the Writer's draft in place; claim splitting and grounding are in `rag/verify.py`."""
from agent.nodes.writer import verifier
from rag.verify import unsupported_count, verify_and_fix, verify_text

__all__ = ["unsupported_count", "verifier", "verify_and_fix", "verify_text"]
