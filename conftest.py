"""Root pytest config: the shared offline fixtures apply to tests/ and to each MCP server's own tests/ folder."""
from tests.conftest import fixture_personas, scripted_llm  # noqa: F401
