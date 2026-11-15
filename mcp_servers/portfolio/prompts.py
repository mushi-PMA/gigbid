"""The Portfolio server's MCP prompts (layout from the brief). Defined in `server.py` with the FastMCP app; the
agents' own prompts live in `agent/prompts/`."""
from mcp_servers.portfolio.server import answer_screening_question, fit_summary, proposal_opening

__all__ = ["answer_screening_question", "fit_summary", "proposal_opening"]
