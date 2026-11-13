"""Ingest a public GitHub repository into a persona's portfolio through the official GitHub MCP server.

Third-party server: https://api.githubcopilot.com/mcp/ (GitHub's own remote MCP server), authenticated with a
fine-grained personal access token that has read-only Contents access (GITHUB_PERSONAL_ACCESS_TOKEN). We only call
read tools (`get_file_contents`). Files land in data/personas/<persona>/repos/<repo>/ and the index is updated
incrementally.

    python -m rag.ingest.github --persona ai_ml_engineer --repo owner/name [--max-files 12]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

from common.config import ROOT
from rag.ingest.loaders import CODE_SUFFIXES

GITHUB_MCP_URL = os.environ.get("GITHUB_MCP_URL", "https://api.githubcopilot.com/mcp/")
MAX_FILE_BYTES = 60_000


def _client() -> MultiServerMCPClient:
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_PERSONAL_ACCESS_TOKEN (read-only Contents) to use the GitHub MCP server")
    return MultiServerMCPClient({"github": {"transport": "streamable_http", "url": GITHUB_MCP_URL,
                                            "headers": {"Authorization": f"Bearer {token}"}}})


def _parse(result) -> object:
    """GitHub MCP returns text or embedded resources; normalise to Python data or text."""
    for item in getattr(result, "content", []) or []:
        resource = getattr(item, "resource", None)
        if resource is not None:
            if getattr(resource, "text", None) is not None:
                return resource.text
            if getattr(resource, "blob", None) is not None:
                return base64.b64decode(resource.blob).decode("utf-8", errors="ignore")
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except ValueError:
                return text
    return None


async def ingest_repo(persona: str, owner: str, repo: str, max_files: int = 12) -> list[str]:
    target = ROOT / "data" / "personas" / persona / "repos" / repo
    saved: list[str] = []
    async with _client().session("github") as session:
        async def contents(path: str):
            return _parse(await session.call_tool("get_file_contents", {"owner": owner, "repo": repo, "path": path}))

        queue = ["/"]
        while queue and len(saved) < max_files:
            listing = await contents(queue.pop(0))
            if not isinstance(listing, list):
                continue
            for entry in listing:
                path, kind = entry.get("path", ""), entry.get("type")
                if kind == "dir" and path.count("/") < 2 and not path.startswith((".", "node_modules")):
                    queue.append(path)
                elif kind == "file" and (path.lower() == "readme.md" or Path(path).suffix.lower() in CODE_SUFFIXES):
                    if entry.get("size", 0) > MAX_FILE_BYTES:
                        continue
                    text = await contents(path)
                    if isinstance(text, str):
                        out = target / ("README.md" if path.lower() == "readme.md" else path)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text(text, encoding="utf-8")
                        saved.append(path)
                if len(saved) >= max_files:
                    break
    return saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", required=True)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--max-files", type=int, default=12)
    args = parser.parse_args()
    owner, name = args.repo.split("/", 1)
    saved = asyncio.run(ingest_repo(args.persona, owner, name, args.max_files))
    print(f"saved {len(saved)} files from {args.repo}")
    from rag.index.store import EvidenceIndex, build_index
    from rag.ingest.loaders import load_persona

    index = build_index(args.persona, load_persona(args.persona), previous=EvidenceIndex.load(args.persona))
    index.save()
    print(f"re-embedded {getattr(index, 'reindexed_documents', '?')} documents")


if __name__ == "__main__":
    main()
