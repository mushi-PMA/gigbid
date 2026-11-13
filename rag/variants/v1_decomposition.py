"""V1 requirement decomposition: one retrieval per extracted requirement, then merge.

Requirements come from the Job Analyst's JobSpec when the graph runs. In offline evaluation they are extracted with
the `rag_helper` model from the job post alone.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agent.prompts import load_prompt
from common.llm import complete_json
from rag.variants.base import Query

NAME = "v1"
GROUP = "query"


class _Requirements(BaseModel):
    requirements: list[str] = Field(description="3 to 7 short, specific requirements of the job, one each")


def decompose(job_text: str) -> list[str]:
    result = complete_json("rag_helper", load_prompt("rag_decompose"), f"<job_post>\n{job_text[:4000]}\n</job_post>",
                           _Requirements)
    return [r.strip() for r in result.requirements if r.strip()][:7]


def queries(job_text: str, requirements: list[dict]) -> list[Query]:
    if requirements:
        return [Query(r["text"], r.get("requirement_id", f"r{i}")) for i, r in enumerate(requirements, 1)]
    return [Query(text, f"r{i}") for i, text in enumerate(decompose(job_text), 1)] or [Query(job_text)]
