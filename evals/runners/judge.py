"""Rubric judge for proposal quality (calibrated against human labels in judge_calibration.py)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from agent.nodes.guards import delimit
from agent.prompts import load_prompt
from common.llm import complete_json


class JudgeScore(BaseModel):
    relevance: int = Field(ge=1, le=5)
    specificity: int = Field(ge=1, le=5)
    personalisation: int = Field(ge=1, le=5)
    credibility: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    reason: str = ""


def judge(job: dict, cover_letter: str) -> JudgeScore:
    user = (f"Job post:\n{delimit('job_post', job['title'] + chr(10) + job['description'][:3000])}\n\n"
            f"Proposal:\n{cover_letter}")
    return complete_json("judge", load_prompt("judge"), user, JudgeScore)
