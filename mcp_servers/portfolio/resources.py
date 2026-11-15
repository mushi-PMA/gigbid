"""The Portfolio server's resources (layout from the brief): case studies, proposals, repositories and the CV as
`portfolio://` URIs. Defined in `server.py` with the FastMCP app."""
from mcp_servers.portfolio.server import case_resource, cv_resource, proposal_resource, repo_resource

__all__ = ["case_resource", "cv_resource", "proposal_resource", "repo_resource"]
