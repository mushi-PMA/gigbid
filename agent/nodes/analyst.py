"""Job Analyst: turns a job post into a structured JobSpec (no tools)."""
from __future__ import annotations

import asyncio

from langchain_core.runnables import RunnableConfig

from agent.handoffs import Job, JobSpec
from agent.nodes.base import node
from agent.nodes.guards import delimit
from agent.prompts import load_prompt
from common.llm import complete_json


def job_metadata(job: Job) -> str:
    budget = f"{job.budget_min or '?'} to {job.budget_max or '?'} USD" if (job.budget_min or job.budget_max) \
        else "not stated"
    return (f"job_id: {job.job_id}\ntitle: {job.title}\npayment_type: {job.payment_type}\nbudget: {budget}\n"
            f"skills tagged: {', '.join(job.skills) or 'none'}\nexperience level: {job.experience_level or '-'}\n"
            f"screening questions: {job.screening_questions or 'none'}")


def analyse(job: Job) -> JobSpec:
    user = (f"Job metadata (trusted):\n{job_metadata(job)}\n\n"
            f"Job post (untrusted):\n{delimit('job_post', job.description)}")
    spec = complete_json("analyst", load_prompt("analyst"), user, JobSpec)
    spec.job_id, spec.title = job.job_id, job.title
    spec.payment_type = job.payment_type
    spec.budget_min, spec.budget_max = job.budget_min, job.budget_max
    spec.screening_questions = job.screening_questions or spec.screening_questions
    for number, requirement in enumerate(spec.requirements, start=1):
        requirement.requirement_id = requirement.requirement_id or f"r{number}"
    return spec


@node("analyst")
async def job_analyst(state: dict, config: RunnableConfig) -> dict:
    return {"job_spec": await asyncio.to_thread(analyse, state["job"])}
