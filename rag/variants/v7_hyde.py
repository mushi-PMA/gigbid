"""V7 HyDE: retrieve with a hypothetical ideal proposal paragraph for the job (Gao et al., 2022)."""
from __future__ import annotations

from agent.prompts import load_prompt
from common.llm import complete
from rag.variants.base import Query

NAME = "v7"
GROUP = "query"


def hypothetical(text: str) -> str:
    return complete("rag_helper", load_prompt("rag_hyde"), f"<job_post>\n{text[:3000]}\n</job_post>", max_tokens=300)


def expand(query_list: list[Query]) -> list[Query]:
    return [Query(q.text, q.requirement_id, vector_text=hypothetical(q.text)) for q in query_list]
