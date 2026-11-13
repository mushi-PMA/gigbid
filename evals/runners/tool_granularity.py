"""R&D question A: does tool granularity change agent behaviour?

40 tasks with known correct calls (generated from the GigSim seed and the personas, saved to
evals/datasets/tool_tasks.json) are given to the same model with native tool calling, under three tool sets:
- fine:   18 narrow tools (job title, job budget, client rating, case-study search, repo search, ...)
- coarse: 3 tools (marketplace / portfolio / workspace) with an `action` enum and a free `params` object
- best:   GigBid's real MCP tool schemas with rewritten descriptions (when to use, what it returns, an example)
Metrics: tool-selection accuracy, argument accuracy, input+output tokens per task.

    python -m evals.runners.tool_granularity
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random

from common.config import ROOT
from common.llm import complete_tools, start_usage
from evals.runners.common import enable_cache, write_result

TASKS_FILE = ROOT / "evals" / "datasets" / "tool_tasks.json"
SYSTEM = ("You help a freelancer by calling exactly one tool for the request. Use the most specific tool that "
          "answers it, with exact ids from the request. Do not answer in text.")


def _obj(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


S = {"type": "string"}
FINE = [
    ("search_jobs_by_keyword", "Search open jobs by words in the title or description.", _obj({"query": S}, ["query"])),
    ("search_jobs_by_skill", "Search open jobs tagged with one skill.", _obj({"skill": S}, ["skill"])),
    ("get_job_title", "Title of one job.", _obj({"job_id": S}, ["job_id"])),
    ("get_job_description", "Full description text of one job post.", _obj({"job_id": S}, ["job_id"])),
    ("get_job_budget", "Budget and payment type of one job.", _obj({"job_id": S}, ["job_id"])),
    ("get_client_rating", "Average rating of a client.", _obj({"client_id": S}, ["client_id"])),
    ("get_client_spend", "Total money a client has spent.", _obj({"client_id": S}, ["client_id"])),
    ("get_client_payment_verified", "Whether the client's payment method is verified.",
     _obj({"client_id": S}, ["client_id"])),
    ("get_connects_balance", "Connects left.", _obj({}, [])),
    ("get_fixed_price_stats", "Fixed-price budget percentiles for a category.", _obj({"category": S}, ["category"])),
    ("get_hourly_rate_stats", "Hourly rate percentiles for a category.", _obj({"category": S}, ["category"])),
    ("search_case_studies", "Search the freelancer's case studies.", _obj({"query": S}, ["query"])),
    ("search_repos", "Search the freelancer's repositories.", _obj({"query": S}, ["query"])),
    ("search_past_proposals", "Search the freelancer's past proposals.", _obj({"query": S}, ["query"])),
    ("get_case_study", "Full text of one case study.", _obj({"case_id": S}, ["case_id"])),
    ("list_skills", "Skills in the portfolio.", _obj({}, [])),
    ("get_free_slots", "Free calendar slots.", _obj({"from_date": S, "duration_minutes": {"type": "integer"}},
                                                    ["from_date"])),
    ("create_email_draft", "Save an email draft.", _obj({"recipient_label": S, "subject": S, "body": S},
                                                        ["subject", "body"])),
]
COARSE = [
    ("marketplace", "Marketplace operations.", _obj({"action": {"type": "string", "enum": [
        "search_jobs", "get_job", "get_client", "get_connects", "get_pricing"]}, "params": {"type": "object"}},
        ["action"])),
    ("portfolio", "Portfolio operations.", _obj({"action": {"type": "string", "enum": [
        "search", "get_case_study", "list_skills"]}, "params": {"type": "object"}}, ["action"])),
    ("workspace", "Calendar and email.", _obj({"action": {"type": "string", "enum": ["free_slots", "email_draft"]},
                                               "params": {"type": "object"}}, ["action"])),
]
BEST_DESCRIPTIONS = {
    "search_jobs": "Find open jobs. Use for 'find/show me jobs about X'. Put topic words in `query` and skill names "
                   "in `skills`. Returns newest jobs with ids. Example: query='airflow pipeline', skills=['Python'].",
    "get_job": "Read ONE job post in full (title, description, budget, screening questions) by its job_id. Use when "
               "the request names a job id.",
    "get_client_history": "Check whether a client is trustworthy: payment verified, total spent, hires, rating, "
                          "feedback. Use for any question about a client id.",
    "get_connects_balance": "How many Connects are left this week. No arguments.",
    "get_market_pricing": "Typical budgets and hourly rates (p25, p50, p75) of comparable jobs. Use for 'what should "
                          "I charge', 'going rate'. Pass the category and/or skills.",
    "search_evidence": "Find proof in MY portfolio (case studies, repos, past proposals) for one requirement. Use for "
                       "'have I done X', 'find my work on X'. Put the requirement in `requirement`.",
    "get_case_study": "Read ONE of my case studies in full by its id (like cs-aiml-03).",
    "list_skills": "List the skills my portfolio shows, with counts. No arguments.",
    "get_free_slots": "Free times in my calendar for a meeting. `from_date` is YYYY-MM-DD; set duration_minutes.",
    "create_email_draft": "Save (never send) an email draft. Give recipient_label, subject and body.",
}

# canonical tool -> what counts as the right tool in each set (fine: any listed; coarse: tool + action)
FINE_OK = {"search_jobs": {"search_jobs_by_keyword", "search_jobs_by_skill"},
           "get_job": {"get_job_description", "get_job_title", "get_job_budget"},
           "get_client_history": {"get_client_rating", "get_client_spend", "get_client_payment_verified"},
           "get_connects_balance": {"get_connects_balance"},
           "get_market_pricing": {"get_fixed_price_stats", "get_hourly_rate_stats"},
           "search_evidence": {"search_case_studies", "search_repos", "search_past_proposals"},
           "get_case_study": {"get_case_study"}, "list_skills": {"list_skills"}, "get_free_slots": {"get_free_slots"},
           "create_email_draft": {"create_email_draft"}}
COARSE_OK = {"search_jobs": ("marketplace", "search_jobs"), "get_job": ("marketplace", "get_job"),
             "get_client_history": ("marketplace", "get_client"),
             "get_connects_balance": ("marketplace", "get_connects"),
             "get_market_pricing": ("marketplace", "get_pricing"), "search_evidence": ("portfolio", "search"),
             "get_case_study": ("portfolio", "get_case_study"), "list_skills": ("portfolio", "list_skills"),
             "get_free_slots": ("workspace", "free_slots"), "create_email_draft": ("workspace", "email_draft")}


def make_tasks() -> list[dict]:
    """40 tasks (4 per canonical tool) with the expected tool and the argument value that must appear."""
    rng = random.Random(2026)
    jobs = [json.loads(line) for line in (ROOT / "data" / "gigsim" / "jobs.jsonl").read_text(encoding="utf-8")
            .splitlines() if line.strip()]
    jobs = [j for j in jobs if j.get("kind") == "regular"]
    picks = rng.sample(jobs, 8)
    cases = sorted(p.stem for p in (ROOT / "data" / "personas" / "ai_ml_engineer" / "case_studies").glob("*.md"))
    topics = ["Airflow data pipelines", "React dashboards", "churn prediction", "Power BI reports"]
    tasks = []
    for topic in topics:
        tasks.append({"request": f"Find me new jobs about {topic}.", "tool": "search_jobs",
                      "arg": ("query_or_skill", topic.split()[0])})
    for job in picks[:4]:
        tasks.append({"request": f"Show me the full post for job {job['job_id']}.", "tool": "get_job",
                      "arg": ("job_id", job["job_id"])})
    for job in picks[4:8]:
        tasks.append({"request": f"Is client {job['client_id']} trustworthy? Check their history.",
                      "tool": "get_client_history", "arg": ("client_id", job["client_id"])})
    for text in ["How many Connects do I have left?", "Can I still afford to bid this week?",
                 "What's my Connects balance?", "Check my remaining Connects."]:
        tasks.append({"request": text, "tool": "get_connects_balance", "arg": None})
    for topic in ["Machine Learning", "Web Development", "Data Analysis", "Microsoft Power BI"]:
        tasks.append({"request": f"What do clients usually pay for {topic} work?", "tool": "get_market_pricing",
                      "arg": ("category_or_skill", topic.split()[0])})
    for topic, keyword in [("a FastAPI service", "FastAPI"), ("an Airflow DAG", "Airflow"),
                           ("a demand forecasting model", "forecast"), ("an NLP classifier", "NLP")]:
        tasks.append({"request": f"Have I ever built {topic}? Find my work on it.", "tool": "search_evidence",
                      "arg": ("query_or_requirement", keyword)})
    for case in cases[:4]:
        tasks.append({"request": f"Open my case study {case} in full.", "tool": "get_case_study",
                      "arg": ("case_id", case)})
    for text in ["Which skills does my portfolio show?", "List my skills.", "What am I strongest at, by evidence?",
                 "Give me my skill list with counts."]:
        tasks.append({"request": text, "tool": "list_skills", "arg": None})
    for date in ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]:
        tasks.append({"request": f"Find free 30-minute slots from {date} for an interview.", "tool": "get_free_slots",
                      "arg": ("from_date", date)})
    for subject in ["Interview times", "Project kickoff", "Invoice question", "Follow-up"]:
        tasks.append({"request": f"Draft an email to the client with subject '{subject}' proposing a call.",
                      "tool": "create_email_draft", "arg": ("subject", subject)})
    return tasks


def _values(arguments: dict) -> str:
    return json.dumps(arguments).lower()


def score(task: dict, toolset: str, calls: list[dict]) -> tuple[bool, bool]:
    if not calls:
        return False, False
    call = calls[0]
    if toolset == "fine":
        selected = call["name"] in FINE_OK[task["tool"]]
    elif toolset == "coarse":
        tool, action = COARSE_OK[task["tool"]]
        selected = call["name"] == tool and call["arguments"].get("action") == action
    else:
        selected = call["name"] == task["tool"]
    if not selected:
        return False, False
    if task["arg"] is None:
        return True, True
    return True, task["arg"][1].lower() in _values(call["arguments"])


async def best_tools() -> list[dict]:
    from mcp.shared.memory import create_connected_server_and_client_session

    from agent.inmemory import load_servers

    tools = []
    for server in load_servers().values():
        async with create_connected_server_and_client_session(server._mcp_server) as session:
            for tool in (await session.list_tools()).tools:
                if tool.name in BEST_DESCRIPTIONS:
                    tools.append({"name": tool.name, "description": BEST_DESCRIPTIONS[tool.name],
                                  "input_schema": tool.inputSchema})
    return tools


def as_specs(rows) -> list[dict]:
    return [{"name": n, "description": d, "input_schema": s} for n, d, s in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    enable_cache("tools")
    tasks = make_tasks()
    TASKS_FILE.write_text(json.dumps(tasks, indent=1), encoding="utf-8")
    toolsets = {"fine": as_specs(FINE), "coarse": as_specs(COARSE), "best": asyncio.run(best_tools())}
    results = {}
    for name, tools in toolsets.items():
        rows = []
        for task in tasks:
            usage = start_usage()
            calls = complete_tools("tool_agent", SYSTEM, task["request"], tools)
            selected, argument = score(task, name, calls)
            rows.append({"request": task["request"], "expected": task["tool"], "calls": calls, "selected": selected,
                         "argument": argument, "tokens": usage.total_tokens})
        results[name] = {"tools": len(tools), "selection_accuracy": round(sum(r["selected"] for r in rows) / 40, 4),
                         "argument_accuracy": round(sum(r["argument"] for r in rows) / 40, 4),
                         "tokens_per_task": round(sum(r["tokens"] for r in rows) / 40), "rows": rows}
        print(f"{name:>6}: selection {results[name]['selection_accuracy']:.2%}, arguments "
              f"{results[name]['argument_accuracy']:.2%}, tokens/task {results[name]['tokens_per_task']}")
    write_result("tool_granularity", {"n_tasks": len(tasks), "results": results})


if __name__ == "__main__":
    main()
