"""Load the real Kaggle job data, clean it, classify it and compute pricing statistics."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from typing import Iterator

import numpy as np

from data.build.download import raw_path
from data.build.skills import canonical_skill, expand_skills

SOURCE_60K = "kaggle:ahmedmyalo/upwork-freelance-jobs-60k"
SOURCE_2024 = "kaggle:asaniczka/upwork-job-postings-dataset-2024-50k-records"
SOURCE_CONTRACTS = "kaggle:asaniczka/freelance-contracts-dataset-1-3-million-entries"

CATEGORIES = ["AI & Machine Learning", "Data Analytics & BI", "Web Development", "Mobile Development",
              "Design & 3D", "Marketing & Sales", "Admin & Data Entry", "Other Development", "Other"]

# tags in the dataset that describe the client or the industry, not a skill
NOT_SKILL_RE = re.compile(
    r"^(business with|tech & it|education$|health & wellness|retail|fashion|real estate|food|media & ent|"
    r"manufacturing|finance & acc|english|smartphone|tablet|website$|enterprise|saas$|amazon$|twitter$|"
    r"youtube$|facebook$|instagram$|linkedin$|pinterest$|tiktok$)", re.I)

# text that makes a real post unsuitable as a clean "regular" job (contact details, scam or injection phrases)
UNSAFE_TEXT_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+|(?<!\w)\+?\d[\d\s().-]{8,}\d|whats\s?app|telegram|skype|discord|paypal|"
    r"ignore (all |any )?(previous|prior)|system prompt|as an ai\b|registration fee|unpaid|for free|free sample",
    re.I)

_AI = {"Machine Learning", "Deep Learning", "Natural Language Processing", "Computer Vision",
       "Large Language Models", "Chatbot Development", "Generative AI", "Artificial Intelligence"}
_ANALYTICS = {"Data Analysis", "Business Intelligence", "Data Visualization", "Statistics", "Data Engineering",
              "Reporting", "Dashboard"}
_WEB = {"Web Development", "Front-End Development", "Back-End Development", "WordPress", "Shopify",
        "Responsive Design", "REST API", "HTML", "CSS", "JavaScript", "Node.js", "React", "PHP"}
_MOBILE = {"Mobile App Development", "iOS", "Android", "Flutter", "React Native", "Swift", "Kotlin"}
_DESIGN = {"3D Modeling", "Graphic Design", "Adobe Photoshop", "Blender", "Autodesk AutoCAD", "Logo Design",
           "Adobe Illustrator", "Animation", "Video Editing"}
_ADMIN = {"Data Entry", "Virtual Assistant", "Customer Service", "Administrative Support"}
_TITLE_AI = re.compile(r"machine learning|\bai\b|\bllm|gpt|\bnlp\b|neural|computer vision|chatbot|deep learning|"
                       r"\bml\b|artificial intelligence", re.I)
_TITLE_ANALYTICS = re.compile(r"data analy|power ?bi|tableau|dashboard|data visuali|\bbi\b|excel|analytics|sql|"
                              r"data scientist|statistic|etl|data engineer|reporting", re.I)
_TITLE_ADMIN = re.compile(r"data entry|virtual assistant|transcri|customer (service|support)|admin", re.I)
_TITLE_MOBILE = re.compile(r"android|\bios\b|mobile app|flutter|react native|iphone", re.I)
_TITLE_WEB = re.compile(r"web ?(site|app|develop|design)|full ?stack|front ?end|back ?end|wordpress|shopify|react|"
                        r"node|django|laravel|php|javascript|developer", re.I)
_TITLE_DESIGN = re.compile(r"3d|design|logo|render|animation|video edit|illustrat|photoshop", re.I)
_TITLE_MARKETING = re.compile(r"seo|marketing|ads?\b|social media|lead gen|sales|copywrit|email campaign", re.I)


def classify(title: str, tags: list[str], search_keyword: str = "") -> str:
    """Rule-based category of a job from its title and skill tags."""
    skills = expand_skills(tags)
    if skills & _AI or _TITLE_AI.search(title):
        return CATEGORIES[0]
    if skills & _ADMIN or _TITLE_ADMIN.search(title):
        return CATEGORIES[6]
    if skills & _ANALYTICS or _TITLE_ANALYTICS.search(title):
        return CATEGORIES[1]
    if skills & _MOBILE or _TITLE_MOBILE.search(title):
        return CATEGORIES[3]
    if skills & _WEB or _TITLE_WEB.search(title):
        return CATEGORIES[2]
    if search_keyword == "3D" or skills & _DESIGN or _TITLE_DESIGN.search(title):
        return CATEGORIES[4]
    if search_keyword == "Marketing" or _TITLE_MARKETING.search(title):
        return CATEGORIES[5]
    return CATEGORIES[7] if search_keyword == "Developer" else CATEGORIES[8]


def read_csv(path) -> Iterator[dict]:
    csv.field_size_limit(10**9)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def money(text: str | None) -> float | None:
    cleaned = re.sub(r"[^\d.]", "", text or "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text.replace("\r", ""))).strip()


def load_kaggle_jobs() -> list[dict]:
    """Normalised real jobs. Each dict has the Job fields plus client signals and a `category`."""
    jobs: list[dict] = []
    seen: set[int] = set()
    for index, row in enumerate(read_csv(raw_path("upwork_jobs_60k.csv"))):
        title, description = clean_text(row["Job Title"]), clean_text(row["Description"])
        if len(description) < 120 or len(title) < 5 or UNSAFE_TEXT_RE.search(title + " " + description):
            continue
        fingerprint = hash((title.lower(), description[:200].lower()))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        tags = [row[f"Category_{i}"].strip() for i in range(1, 10) if row[f"Category_{i}"].strip()]
        tags = [t for t in tags if not NOT_SKILL_RE.match(t)][:8]
        if not tags:
            continue
        hourly = row["Payment_type"] == "Hourly"
        if hourly:
            low, high = money(row["Start_rate"]), money(row["End_rate"])
            single = money(row["Hourly_Rate"])
            budget_min, budget_max = (low, high) if low and high else (single, single)
        else:
            budget_min = budget_max = money(row["Job_Cost"])
        connects = int(money(row["New_Connects_Num"]) or money(row["Connects_Num"]) or 4)
        jobs.append({
            "row": index, "title": title, "description": description, "skills": tags,
            "category": classify(title, tags, row["Search_Keyword"]),
            "payment_type": "hourly" if hourly else "fixed",
            "budget_min": budget_min, "budget_max": budget_max,
            "experience_level": {"Entry level": "entry", "Intermediate": "intermediate",
                                 "Expert": "expert"}.get(row["EX_level_demand"], ""),
            "connects_cost": max(1, min(connects, 30)),
            "applicants": row["Applicants_Num"],
            "client": {"country": row["Client_Country"], "payment_verified": row["Payment_Situation"] == "Payment verified",
                       "spent": money(row["Spent($)"]) or 0.0, "rating": money(row["Rating"]),
                       "feedback": int(money(row["Feedback_Num"]) or 0)},
        })
    return jobs


# ---------------------------------------------------------------------------------------------------------
# Pricing statistics
# ---------------------------------------------------------------------------------------------------------

def price_value(job: dict) -> tuple[str, float] | None:
    """(payment_type, typical amount) of a normalised job, or None when the post gave no budget."""
    if job["budget_max"] is None:
        return None
    if job["payment_type"] == "hourly":
        value = (job["budget_min"] + job["budget_max"]) / 2
        return ("hourly", value) if 3 <= value <= 300 else None
    return ("fixed", job["budget_max"]) if 10 <= job["budget_max"] <= 50000 else None


def percentiles(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p25": None, "p50": None, "p75": None}
    p25, p50, p75 = np.percentile(values, [25, 50, 75])
    return {"n": len(values), "p25": round(float(p25), 2), "p50": round(float(p50), 2), "p75": round(float(p75), 2)}


def _extra_samples_2024() -> list[tuple[str, str, float]]:
    """(category, payment type, amount) from the 2024 postings; category comes from the title only."""
    samples = []
    for row in read_csv(raw_path("upwork_jobs_2024.csv")):
        category = classify(row["title"], [])
        if category in ("Other", "Other Development"):
            continue
        if row["is_hourly"] == "True":
            low, high = money(row["hourly_low"]), money(row["hourly_high"])
            if low and high and 3 <= (low + high) / 2 <= 300:
                samples.append((category, "hourly", (low + high) / 2))
        else:
            budget = money(row["budget"])
            if budget and 10 <= budget <= 50000:
                samples.append((category, "fixed", budget))
    return samples


def _extra_samples_contracts() -> list[tuple[str, str, float]]:
    """Hourly rates actually paid in finished contracts, grouped by a category read from the job title."""
    samples = []
    quick = re.compile(r"data|python|machine|\bai\b|ml|web|react|node|developer|website|power ?bi|tableau|excel|sql|"
                       r"wordpress|shopify|android|ios|app", re.I)
    for row in read_csv(raw_path("contracts.csv")):
        title = row["job_title"]
        rate, hours = money(row["hourly_rate"]), money(row["total_hours"])
        if not rate or not hours or hours < 10 or not 3 <= rate <= 300 or not quick.search(title):
            continue
        category = classify(title, [])
        if category not in ("Other", "Other Development"):
            samples.append((category, "hourly", rate))
    return samples


EXTRA_CAP = 1500


def build_pricing(pool: list[dict], persona_skills: dict[str, set[str]]) -> dict:
    """Percentiles per category, per skill and per persona market, for fixed and hourly jobs."""
    by_category: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"fixed": [], "hourly": []})
    by_skill: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"fixed": [], "hourly": []})
    by_persona: dict[str, dict[str, list[float]]] = {p: {"fixed": [], "hourly": []} for p in persona_skills}
    everything: dict[str, list[float]] = {"fixed": [], "hourly": []}
    for job in pool:
        priced = price_value(job)
        if not priced:
            continue
        kind, value = priced
        by_category[job["category"]][kind].append(value)
        everything[kind].append(value)
        canon = {canonical_skill(s) for s in job["skills"]}
        for skill in canon:
            by_skill[skill][kind].append(value)
        for persona, skillset in persona_skills.items():
            if len(canon & skillset) / len(canon) >= 0.5:
                by_persona[persona][kind].append(value)
    # the extra sources are huge, so keep a fixed-seed sample per category and payment type
    rng = np.random.default_rng(2026)
    extras: dict[tuple[str, str], list[float]] = defaultdict(list)
    for category, kind, value in _extra_samples_2024() + _extra_samples_contracts():
        extras[(category, kind)].append(value)
    for (category, kind), values in sorted(extras.items()):
        if len(values) > EXTRA_CAP:
            values = list(rng.choice(values, EXTRA_CAP, replace=False))
        by_category[category][kind].extend(values)

    def stats(group: dict[str, list[float]]) -> dict:
        return {"n": len(group["fixed"]) + len(group["hourly"]), "fixed": percentiles(group["fixed"]),
                "hourly": percentiles(group["hourly"])}

    return {
        "note": "p25/p50/p75 of budgets from real historical postings (fixed: budget in USD, hourly: mid of the "
                "hourly range) plus the 2024 postings and finished-contract hourly rates for category level.",
        "all": stats(everything),
        "categories": {c: stats(g) for c, g in sorted(by_category.items())},
        "skills": {s: stats(g) for s, g in sorted(by_skill.items()) if len(g["fixed"]) + len(g["hourly"]) >= 15},
        "personas": {p: stats(g) for p, g in by_persona.items()},
    }
