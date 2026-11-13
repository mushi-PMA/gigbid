"""Load a persona's portfolio into evidence documents with metadata.

Sources: CV (PDF), case studies (Markdown with front matter), repo READMEs and code (local folder or the GitHub
MCP server, see github.py), client reviews and past proposals with outcomes. Every document carries: persona, type,
project, skills, date, client industry and, for proposals, outcome.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from common.config import ROOT

PERSONAS_DIR = ROOT / "data" / "personas"
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".sql", ".ipynb", ".yaml", ".yml", ".toml", ".r", ".dbt"}


@dataclass
class Document:
    evidence_id: str
    persona: str
    type: str                 # cv | case_study | readme | code | review | proposal
    text: str
    title: str = ""
    project: str = ""
    skills: list[str] = field(default_factory=list)
    date: str = ""
    client_industry: str = ""
    outcome: str = ""
    source: str = ""

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.text}".encode()).hexdigest()[:16]

    def metadata(self) -> dict:
        return {"persona": self.persona, "type": self.type, "title": self.title, "project": self.project,
                "skills": self.skills, "date": self.date, "client_industry": self.client_industry,
                "outcome": self.outcome, "source": self.source}


def _front_matter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            meta = yaml.safe_load(text[3:end]) or {}
            return meta, text[end + 4:].lstrip()
    return {}, text


def _project_index(persona_dir: Path) -> dict[str, dict]:
    """Map artifact references to their project (used only to attach project metadata, never gold labels)."""
    path = persona_dir / "projects.json"
    if not path.exists():
        return {}
    index: dict[str, dict] = {}
    for project in json.loads(path.read_text(encoding="utf-8")):
        for artifact in project.get("artifacts", []):
            index[artifact] = project
    return index


def load_cv(persona: str, persona_dir: Path) -> list[Document]:
    path = persona_dir / "cv.pdf"
    if not path.exists():
        return []
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return [Document(f"{persona}:cv", persona, "cv", text, title="Curriculum vitae", source=str(path.name))]


def load_case_studies(persona: str, persona_dir: Path, projects: dict[str, dict]) -> list[Document]:
    docs = []
    for path in sorted((persona_dir / "case_studies").glob("*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        case_id = str(meta.get("id", path.stem))
        project = projects.get(f"case_study:{case_id}", {})
        docs.append(Document(
            f"{persona}:cs:{case_id}", persona, "case_study", body, title=str(meta.get("title", case_id)),
            project=str(meta.get("project", project.get("project_id", ""))),
            skills=list(meta.get("skills", [])), date=str(meta.get("date", "")),
            client_industry=str(meta.get("industry", project.get("industry", ""))), source=f"case_studies/{path.name}"))
    return docs


def load_repos(persona: str, persona_dir: Path, projects: dict[str, dict]) -> list[Document]:
    docs = []
    for repo in sorted(p for p in (persona_dir / "repos").glob("*") if p.is_dir()):
        project = projects.get(f"repo:{repo.name}", {})
        common = dict(project=project.get("project_id", ""), date=str(project.get("year", "")),
                      client_industry=project.get("industry", ""))
        readme = repo / "README.md"
        if readme.exists():
            docs.append(Document(f"{persona}:readme:{repo.name}", persona, "readme",
                                 readme.read_text(encoding="utf-8"), title=f"{repo.name} README",
                                 source=f"repos/{repo.name}/README.md", **common))
        for code in sorted(repo.rglob("*")):
            if code.is_file() and code.suffix.lower() in CODE_SUFFIXES:
                relative = code.relative_to(repo).as_posix()
                docs.append(Document(f"{persona}:code:{repo.name}/{relative}", persona, "code",
                                     code.read_text(encoding="utf-8", errors="ignore"),
                                     title=f"{repo.name}/{relative}", source=f"repos/{repo.name}/{relative}",
                                     **common))
    return docs


def load_reviews(persona: str, persona_dir: Path) -> list[Document]:
    path = persona_dir / "reviews.json"
    if not path.exists():
        return []
    docs = []
    for number, review in enumerate(json.loads(path.read_text(encoding="utf-8")), start=1):
        review_id = str(review.get("review_id", number))
        docs.append(Document(f"{persona}:review:{review_id}", persona, "review", review.get("text", ""),
                             title=f"Client review {review_id}", project=review.get("project_id", ""),
                             date=str(review.get("date", "")), client_industry=review.get("client_industry", ""),
                             outcome=str(review.get("rating", "")), source="reviews.json"))
    return docs


def load_proposals(persona: str, persona_dir: Path) -> list[Document]:
    path = persona_dir / "proposals.json"
    if not path.exists():
        return []
    docs = []
    for proposal in json.loads(path.read_text(encoding="utf-8")):
        project_ids = proposal.get("project_ids") or [""]
        docs.append(Document(
            f"{persona}:proposal:{proposal['proposal_id']}", persona, "proposal", proposal.get("text", ""),
            title=f"Past proposal: {proposal.get('job_title', '')}", project=project_ids[0],
            skills=list(proposal.get("job_skills", [])), date=str(proposal.get("date", "")),
            client_industry=proposal.get("client_industry", ""), outcome=proposal.get("outcome", ""),
            source="proposals.json"))
    return docs


def load_persona(persona: str, base: Path | None = None) -> list[Document]:
    persona_dir = (base or PERSONAS_DIR) / persona
    projects = _project_index(persona_dir)
    return (load_cv(persona, persona_dir) + load_case_studies(persona, persona_dir, projects)
            + load_repos(persona, persona_dir, projects) + load_reviews(persona, persona_dir)
            + load_proposals(persona, persona_dir))


def list_personas(base: Path | None = None) -> list[str]:
    return sorted(p.name for p in (base or PERSONAS_DIR).glob("*") if (p / "profile.json").exists())
