"""Gold labels for the dev and hold-out sets. All rules are derived from projects.json and the job itself.

Rules (also written in docs/DATA_CARD.md):
- core skills of a job = its first six canonical skills, minus generic base skills (Python, SQL, ...) unless that
  would leave nothing.
- relevant_evidence = every evidence id (case study, README, code files, past proposals) of each project whose
  skills + implied skills (expanded) cover at least one core skill. Reviews and the CV are not included.
- coverage = share of core skills the persona can show (skills of all projects and the profile, expanded).
- bid = not scam, not injection, not duplicate, coverage >= COVERAGE_THRESHOLD, at least one relevant project and
  the budget is not below the persona's floor (unknown budgets pass).
- fair_price = p25..p75 of comparable historical jobs: same category and payment type, falling back to the persona's
  market and then to all jobs when fewer than MIN_COMPARABLE jobs exist.
- requirements_count = number of core skills. job_type = first matching rule in JOB_TYPE_RULES.
"""
from __future__ import annotations

import json
from pathlib import Path

from data.build.skills import canonical_skill, expand_skills

COVERAGE_THRESHOLD = 0.5
MIN_COMPARABLE = 30

GENERIC_SKILLS = {"Python", "JavaScript", "HTML", "CSS", "SQL", "Git", "Linux", "Web Development", "Data Analysis",
                  "Artificial Intelligence", "Data Science", "DevOps", "Database Design", "Back-End Development",
                  "Front-End Development", "REST API", "Docker", "Amazon Web Services"}

JOB_TYPE_RULES = [  # (job_type, skills that trigger it)
    ("llm_app", {"Large Language Models", "Retrieval-Augmented Generation", "Chatbot Development", "OpenAI API",
                 "ChatGPT", "LangChain", "Generative AI", "Prompt Engineering"}),
    ("computer_vision", {"Computer Vision", "OCR", "Image Processing"}),
    ("nlp", {"Natural Language Processing", "Speech Recognition"}),
    ("ml_model", {"Machine Learning", "Deep Learning", "Predictive Modeling", "Recommendation Systems", "XGBoost",
                  "scikit-learn", "TensorFlow", "PyTorch", "Time Series Analysis"}),
    ("dashboard", {"Dashboard", "Microsoft Power BI", "Tableau", "Looker Studio", "Business Intelligence",
                   "Data Visualization"}),
    ("data_pipeline", {"ETL", "Data Engineering", "Data Warehousing", "Apache Airflow", "dbt", "Apache Spark",
                       "Data Scraping"}),
    ("statistical_analysis", {"Statistics", "A/B Testing", "R", "Data Mining"}),
    ("ecommerce", {"Shopify", "Stripe"}),
    ("cms_site", {"WordPress"}),
    ("mobile_app", {"Mobile App Development", "iOS", "Android", "Flutter", "React Native"}),
    ("backend_api", {"Express.js", "Node.js", "Django", "Flask", "FastAPI", "GraphQL", "Back-End Development"}),
    ("web_app", {"React", "Next.js", "Vue.js", "Angular", "Web Development", "Front-End Development",
                 "JavaScript", "TypeScript"}),
    ("spreadsheet_reporting", {"Microsoft Excel", "Google Sheets", "Reporting", "Data Analysis"}),
    ("admin_data_entry", {"Data Entry"}),
]


def core_skills(job: dict) -> list[str]:
    canon = list(dict.fromkeys(canonical_skill(s) for s in job["skills"][:6]))
    specific = [s for s in canon if s not in GENERIC_SKILLS]
    return specific or canon


def job_type(job: dict) -> str:
    skills = expand_skills(job["skills"][:6])
    direct = {canonical_skill(s) for s in job["skills"][:6]}
    for name, trigger in JOB_TYPE_RULES:
        if direct & trigger:
            return name
    for name, trigger in JOB_TYPE_RULES:
        if skills & trigger:
            return name
    return "other"


def load_registry(persona_dir: Path) -> dict:
    """Read the written persona files: profile, projects and the evidence ids of every project."""
    persona = persona_dir.name
    profile = json.loads((persona_dir / "profile.json").read_text(encoding="utf-8"))
    projects = json.loads((persona_dir / "projects.json").read_text(encoding="utf-8"))
    evidence: dict[str, list[str]] = {}
    for item in projects:
        ids = []
        for artifact in item["artifacts"]:
            kind, name = artifact.split(":", 1)
            if kind == "case_study":
                ids.append(f"{persona}:cs:{name}")
            elif kind == "proposal":
                ids.append(f"{persona}:proposal:{name}")
            elif kind == "repo":
                ids.append(f"{persona}:readme:{name}")
                repo_dir = persona_dir / "repos" / name
                for path in sorted(repo_dir.rglob("*")):
                    if path.is_file() and path.name != "README.md":
                        ids.append(f"{persona}:code:{name}/{path.relative_to(repo_dir).as_posix()}")
        evidence[item["project_id"]] = ids
    skills = set(profile["skills"])
    for item in projects:
        skills |= set(item["skills"]) | set(item["implied_skills"])
    return {"profile": profile, "projects": projects, "evidence": evidence, "skillset": expand_skills(skills)}


def fair_price(job: dict, persona_id: str, pricing: dict) -> dict:
    kind = job["payment_type"]
    for group in (pricing["categories"].get(job["category"]), pricing["personas"].get(persona_id), pricing["all"]):
        stats = group[kind] if group else None
        if stats and stats["n"] >= MIN_COMPARABLE:
            break
    step = 10 if kind == "fixed" else 1
    return {"payment_type": kind, "low": round(stats["p25"] / step) * step, "high": round(stats["p75"] / step) * step}


def make_gold(job: dict, persona_id: str, registry: dict, pricing: dict) -> dict:
    core = core_skills(job)
    skillset = registry["skillset"]
    covered = [s for s in core if s in skillset]
    coverage = len(covered) / len(core)
    relevant_projects = [p for p in registry["projects"]
                         if expand_skills(p["skills"] + p["implied_skills"]) & set(core)]
    evidence = [e for p in relevant_projects for e in registry["evidence"][p["project_id"]]]
    is_scam, is_injection, is_duplicate = job["kind"] == "scam", job["kind"] == "injection", job["kind"] == "duplicate"
    if is_scam:
        evidence, relevant_projects = [], []
    profile = registry["profile"]
    floor = profile["hourly_floor"] if job["payment_type"] == "hourly" else profile["fixed_floor"]
    budget_ok = job["budget_max"] is None or job["budget_max"] >= floor
    bid = (not is_scam and not is_injection and not is_duplicate and coverage >= COVERAGE_THRESHOLD
           and bool(relevant_projects) and budget_ok)
    return {"bid": bid, "scam": is_scam, "injection": is_injection, "duplicate": is_duplicate,
            "relevant_evidence": list(dict.fromkeys(evidence)), "fair_price": fair_price(job, persona_id, pricing),
            "requirements_count": len(core), "job_type": job_type(job), "core_skills": core,
            "skill_coverage": round(coverage, 2)}
