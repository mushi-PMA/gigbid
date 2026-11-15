"""Portfolio MCP server (read-only): evidence search over a freelancer's CV, case studies, repos, reviews and past
proposals, with resource templates and prompt templates a freelancer would actually use.

Standalone use (any MCP host, for example a desktop chat app or Cursor):
    uvx --from git+https://github.com/mushi-PMA/gigbid gigbid-portfolio-mcp --stdio
    env: PORTFOLIO_DIR=<folder with one sub-folder per persona>  PORTFOLIO_PERSONA=<sub-folder name>
Inside GigBid it runs over Streamable HTTP with bearer auth; the persona comes from the caller's token.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from common import audit
from common.security import ServiceTokenVerifier
from common.tracing import setup_tracing, span
from rag.ingest import loaders

SERVER = "portfolio"
PORT = int(os.environ.get("PORTFOLIO_MCP_PORT", "8101"))
PUBLIC_URL = os.environ.get("PORTFOLIO_MCP_URL", f"http://localhost:{PORT}/mcp")
AUTH = os.environ.get("MCP_AUTH", "on") == "on"
if os.environ.get("PORTFOLIO_DIR"):
    loaders.PERSONAS_DIR = Path(os.environ["PORTFOLIO_DIR"])

setup_tracing("mcp-portfolio")
mcp = FastMCP(
    "gigbid-portfolio",
    instructions="Read-only access to a freelancer's portfolio. Use search_evidence to find proof for a job "
                 "requirement, then load full items through the portfolio:// resources.",
    token_verifier=ServiceTokenVerifier() if AUTH else None,
    auth=AuthSettings(issuer_url=os.environ.get("API_PUBLIC_URL", "http://localhost:8000"),
                      resource_server_url=PUBLIC_URL, required_scopes=["portfolio"]) if AUTH else None,
    host=os.environ.get("MCP_HOST", "127.0.0.1"), port=PORT, stateless_http=True, json_response=True)

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
EvidenceType = Literal["cv", "case_study", "readme", "code", "review", "proposal"]


def _persona() -> tuple[str, str]:
    token = get_access_token()
    if token is not None and token.claims:
        return token.claims["sub"], token.claims.get("persona", "")
    persona = os.environ.get("PORTFOLIO_PERSONA") or (loaders.list_personas(loaders.PERSONAS_DIR) or [""])[0]
    return "local", persona


def _persona_dir(persona: str) -> Path:
    return loaders.PERSONAS_DIR / persona


class Evidence(BaseModel):
    evidence_id: str
    type: str
    title: str
    project: str = ""
    source: str = ""
    date: str = ""
    outcome: str = Field("", description="For past proposals: won, replied or ignored")
    client_industry: str = ""
    skills: list[str] = Field(default_factory=list)
    excerpt: str
    score: float


class EvidenceSearch(BaseModel):
    requirement: str
    items: list[Evidence]


class EvidenceFilters(BaseModel):
    types: list[EvidenceType] | None = Field(None, description="Only these evidence types")
    outcome: list[Literal["won", "replied", "ignored"]] | None = Field(None, description="Past proposal outcomes")
    skills: list[str] | None = Field(None, description="Only items tagged with one of these skills")


@mcp.tool(annotations=READ, title="Search evidence")
async def search_evidence(
    requirement: Annotated[str, Field(min_length=2, max_length=500, description="One job requirement")],
    k: Annotated[int, Field(ge=1, le=20)] = 5,
    filters: EvidenceFilters | None = None,
) -> EvidenceSearch:
    """Find portfolio evidence that proves one job requirement (shipped retrieval pipeline)."""
    from rag.retriever import Retriever

    user_id, persona = _persona()
    with span("mcp.portfolio.search_evidence", kind="RETRIEVER", requirement=requirement, persona=persona):
        retriever = Retriever(persona)
        # retrieval is CPU and model bound: run it off the event loop so parallel searches do not queue
        items = await asyncio.to_thread(retriever.search_text, requirement, k * 3 if filters else k)
        if filters:
            items = [i for i in items
                     if (not filters.types or i.type in filters.types)
                     and (not filters.outcome or i.outcome in filters.outcome)
                     and (not filters.skills or {s.lower() for s in filters.skills} & {s.lower() for s in i.skills})]
        result = EvidenceSearch(requirement=requirement, items=[
            Evidence(evidence_id=i.evidence_id, type=i.type, title=i.title, project=i.project, source=i.source,
                     date=i.date, outcome=i.outcome, client_industry=i.client_industry, skills=i.skills,
                     excerpt=i.text[:600], score=i.score) for i in items[:k]])
    audit.write(user_id, SERVER, "search_evidence", {"requirement": requirement, "k": k},
                {"ids": [i.evidence_id for i in result.items]}, ok=True)
    return result


class CaseStudy(BaseModel):
    case_id: str
    title: str
    project: str
    date: str
    industry: str
    skills: list[str]
    body: str


@mcp.tool(annotations=READ, title="Get case study")
async def get_case_study(case_id: Annotated[str, Field(min_length=1, max_length=80)]) -> CaseStudy:
    """Full text of one case study (id like 'cs-aiml-03' or the full evidence id)."""
    _, persona = _persona()
    case_id = case_id.split(":")[-1]
    for doc in loaders.load_case_studies(persona, _persona_dir(persona), {}):
        if doc.evidence_id.endswith(f":{case_id}"):
            return CaseStudy(case_id=case_id, title=doc.title, project=doc.project, date=doc.date,
                             industry=doc.client_industry, skills=doc.skills, body=doc.text)
    raise ValueError(f"no case study '{case_id}'")


class SkillCount(BaseModel):
    skill: str
    evidence_count: int


class SkillList(BaseModel):
    persona: str
    skills: list[SkillCount]


@mcp.tool(annotations=READ, title="List skills")
async def list_skills() -> SkillList:
    """Skills in the portfolio with how many evidence items mention each one."""
    _, persona = _persona()
    counts: Counter[str] = Counter()
    profile = json.loads((_persona_dir(persona) / "profile.json").read_text(encoding="utf-8"))
    for doc in loaders.load_persona(persona, loaders.PERSONAS_DIR):
        for skill in set(doc.skills):
            counts[skill] += 1
    for skill in profile.get("skills", []):
        counts.setdefault(skill, 0)
    return SkillList(persona=persona, skills=[SkillCount(skill=s, evidence_count=c) for s, c in counts.most_common()])


# ---------------------------------------------------------------------------------------------------------
# Resources (load full items)
# ---------------------------------------------------------------------------------------------------------


def _find(prefix: str, item_id: str) -> str:
    _, persona = _persona()
    wanted = f"{persona}:{prefix}:{item_id.split(':')[-1]}"
    for doc in loaders.load_persona(persona, loaders.PERSONAS_DIR):
        if doc.evidence_id == wanted:
            meta = json.dumps(doc.metadata(), ensure_ascii=False)
            return f"<!-- {meta} -->\n# {doc.title}\n\n{doc.text}"
    raise ValueError(f"not found: {wanted}")


@mcp.resource("portfolio://case/{case_id}", mime_type="text/markdown")
def case_resource(case_id: str) -> str:
    """A case study in full."""
    return _find("cs", case_id)


@mcp.resource("portfolio://proposal/{proposal_id}", mime_type="text/markdown")
def proposal_resource(proposal_id: str) -> str:
    """A past proposal with its outcome (won, replied or ignored)."""
    return _find("proposal", proposal_id)


@mcp.resource("portfolio://repo/{repo}", mime_type="text/markdown")
def repo_resource(repo: str) -> str:
    """A repository README."""
    return _find("readme", repo)


@mcp.resource("portfolio://cv", mime_type="text/plain")
def cv_resource() -> str:
    """The freelancer's CV as text."""
    _, persona = _persona()
    docs = loaders.load_cv(persona, _persona_dir(persona))
    return docs[0].text if docs else ""


# ---------------------------------------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------------------------------------


@mcp.prompt(title="Answer a screening question from my portfolio")
def answer_screening_question(question: str) -> str:
    return (f"Answer this client screening question in 60 to 120 words, first person, plain English:\n\n{question}\n\n"
            "First call search_evidence with the question. Use only facts from the evidence you find, cite each "
            "fact with its evidence id in brackets, and say plainly if the portfolio has no relevant example.")


@mcp.prompt(title="Write a proposal opening for a job")
def proposal_opening(job_post: str) -> str:
    return ("Write the first two sentences of a proposal for the job below. Open with the client's actual problem, "
            "then the single most relevant past project from my portfolio (call search_evidence first). No "
            "greetings like 'Dear Sir/Madam', no claims without evidence, no contact details.\n\n"
            f"<job_post>\n{job_post}\n</job_post>")


@mcp.prompt(title="How well do I fit this job?")
def fit_summary(job_post: str) -> str:
    return ("List the job's requirements. For each, call search_evidence and say whether my portfolio proves it "
            "(strong, partial, none) with the evidence ids. End with an honest bid or skip recommendation.\n\n"
            f"<job_post>\n{job_post}\n</job_post>")


def main() -> None:
    import sys

    stdio = "--stdio" in sys.argv or not AUTH
    if stdio:
        # Load the retriever (model, index) before stdio starts: on Windows the first load inside a worker thread
        # hangs while the transport blocks on stdin, and it also keeps the first search from timing out the host.
        from rag.retriever import Retriever

        try:
            Retriever(_persona()[1]).search_text("warm up", 1)
        except Exception as error:  # a missing persona folder is reported by the tools themselves
            print(f"portfolio: retriever not ready ({error})", file=sys.stderr)
    mcp.run(transport="stdio" if stdio else "streamable-http")


if __name__ == "__main__":
    main()
