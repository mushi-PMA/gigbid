"""Render one persona (profile, projects, case studies, repos, reviews, proposals, CV) from persona_defs."""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from fpdf import FPDF

from data.build import persona_text as T
from data.build.code_templates import TEMPLATES
from data.build.download import raw_path
from data.build.skills import canonical_skill, expand_skills


def round_to(value: float, step: float) -> float:
    return round(value / step) * step


def sentence(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def persona_skillset(pdef: dict) -> set[str]:
    """Every canonical skill the persona can show, including implied ones. Used for gold labels and for jobs."""
    skills = list(pdef["skills"])
    for item in pdef["projects"]:
        skills += item["skills"] + item["implied_skills"]
    return expand_skills(skills)


# ---------------------------------------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------------------------------------

def experience_premium(primary_skill: str) -> float:
    """Ratio of the median hourly rate of senior (5+ years) freelancers to all freelancers in the rate dataset."""
    everyone, senior = [], []
    with open(raw_path("freelancer_stats.csv"), encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["primary_skill"] != primary_skill or not row["hourly_rate_usd"] or not row["years_experience"]:
                continue
            rate = float(row["hourly_rate_usd"])
            everyone.append(rate)
            if float(row["years_experience"]) >= 5 and float(row["job_success_rate"] or 0) >= 85:
                senior.append(rate)
    if not everyone or not senior:
        return 1.0
    return min(1.3, max(1.0, statistics.median(senior) / statistics.median(everyone)))


def build_profile(pdef: dict, market: dict) -> dict:
    hourly, fixed = market["hourly"], market["fixed"]
    premium = experience_premium(pdef["freelancer_primary_skill"])
    floor = round_to(max(15.0, hourly["p50"] or 25.0), 5)
    target = round_to(max(floor + 5, (hourly["p75"] or 40.0) * premium), 5)
    return {
        "persona_id": pdef["persona_id"], "name": pdef["name"], "headline": pdef["headline"],
        "location": pdef["location"], "years_experience": pdef["years_experience"], "summary": pdef["summary"],
        "education": pdef["education"], "skills": pdef["skills"],
        "hourly_floor": floor, "hourly_target": target,
        "fixed_floor": max(100.0, round_to(fixed["p25"] or 150.0, 50)),
        "weekly_connects_budget": pdef["weekly_connects_budget"],
        "rate_basis": {"market_hourly": hourly, "market_fixed": fixed, "experience_premium": round(premium, 3),
                       "note": "Floor = market median hourly, target = market p75 times the experience premium from the "
                               "freelancer dataset (which is clipped at 280 USD, so only the ratio is used). "
                               "Fixed floor = market p25."},
        "source": "synthetic",
    }


# ---------------------------------------------------------------------------------------------------------
# Projects, case studies, READMEs, code
# ---------------------------------------------------------------------------------------------------------

def project_id(pdef: dict, n: int) -> str:
    return f"p-{pdef['short']}-{n:02d}"


def case_id(pdef: dict, n: int) -> str:
    return f"cs-{pdef['short']}-{n:02d}"


def explicit_line(skill: str, pool: list[str], rng: random.Random) -> str:
    return rng.choice(pool).format(s=skill)


def clue_line(skill: str, rng: random.Random) -> str:
    options = T.CLUES.get(skill)
    return rng.choice(options) if options else ""


def render_case_study(pdef: dict, item: dict, rng: random.Random) -> str:
    listed = rng.sample(item["skills"], k=max(1, math.ceil(len(item["skills"]) * 0.6)))  # only part of the skills
    month = rng.randint(1, 12)
    front = yaml.safe_dump({"id": case_id(pdef, item["n"]), "project": item["name"],
                            "date": f"{item['year']}-{month:02d}", "industry": item["industry"], "skills": listed},
                           sort_keys=False, default_flow_style=None).strip()
    title = rng.choice([item["name"], f"Case study: {item['name']}",
                        f"{sentence(item['short'])} for a {item['client_type']} in {item['industry']}"])
    context = rng.choice(T.CONTEXT_STORY).format(year=item["year"], client_type=item["client_type"],
                                                 industry=item["industry"], problem=item["problem_a"])
    facts = [explicit_line(s, T.EXPLICIT_STORY, rng) for s in item["skills"]]
    facts += [clue_line(s, rng) for s in item["implied_skills"]]
    facts = [f for f in facts if f]
    rng.shuffle(facts)
    if rng.random() < 0.5:
        body = "\n".join(f"- {f}" for f in facts)
    else:
        body = " ".join(facts)
    result = rng.choice(T.RESULT_STORY).format(metric=item["metric"])
    lesson = rng.choice(T.LESSONS)
    return (f"---\n{front}\n---\n\n# {title}\n\n## Context\n\n{context}\n\n## What I did\n\n{body}\n\n"
            f"## Result\n\n{result}\n\n## Looking back\n\n{lesson}\n")


def fill(template: str, entity: str, fields: list[str]) -> str:
    entities = entity + "s"
    pascal = "".join(part.capitalize() for part in entity.split("_"))
    replacements = {"@ENTITIES@": entities, "@ENTITY@": entity, "@Entity@": pascal,
                    "@F1@": fields[0], "@F2@": fields[1], "@F3@": fields[2]}
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def render_repo(pdef: dict, spec: dict, projects: dict[int, dict], rng: random.Random) -> dict[str, str]:
    """Return {relative path: text} for one repo, including README.md."""
    files: dict[str, str] = {}
    for kind in spec["kinds"]:
        path, source = TEMPLATES[kind]
        files[fill(path, spec["entity"], spec["fields"])] = fill(source, spec["entity"], spec["fields"])
    listing = "\n".join(f"- `{path}`" for path in sorted(files))
    setup = T.SETUP.get(spec["language"], T.SETUP["Python"])
    if spec["vague"]:
        readme = (f"# {spec['name']}\n\nScripts and notes from a client engagement. Work in progress, see the code "
                  f"for details.\n\n## Files\n\n{listing}\n\n## Run\n\n```\n{setup}\n```\n")
    else:
        item = projects[spec["projects"][0]]
        stack = ", ".join(item["skills"])
        lines = [explicit_line(s, T.EXPLICIT_TECH, rng) for s in item["skills"][:2]]
        lines += [clue_line(s, rng) for s in item["implied_skills"][:2]]
        notes = "\n".join(f"- {line}" for line in lines if line)
        readme = (f"# {spec['name']}\n\n{sentence(item['problem_b'])}.\n\nStack: {stack}.\n\n## What is in here\n\n"
                  f"{listing}\n\n## Notes\n\n{notes}\n- {rng.choice(T.README_NOTES)}\n\n## Run\n\n```\n{setup}\n```\n")
    files["README.md"] = readme
    return files


# ---------------------------------------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------------------------------------

def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def draw_outcome(rng: random.Random, opening: str, n_evidence: int, overlap: float, question: bool, price_ratio: float,
                 long_text: bool) -> str:
    """Outcome depends on learnable features: specific evidence, personal opening, skill overlap, fair price."""
    z = (-2.6 + {"personal": 1.3, "semi": 0.5, "generic": -1.2}[opening] + 0.9 * (n_evidence >= 1)
         + 0.5 * (n_evidence == 2) + 1.4 * overlap + 0.5 * question - 0.9 * max(0.0, price_ratio - 1.25)
         - 0.4 * long_text + rng.gauss(0, 0.55))
    if rng.random() >= sigmoid(z):
        return "ignored"
    return "won" if rng.random() < sigmoid(z - 1.2) else "replied"


def job_snippet(description: str) -> str:
    first = description.replace('"', "").replace("\n", " ").strip().split(". ")[0]
    return " ".join(first.split()[:9]).rstrip(",;:")


def make_proposal(pdef: dict, number: int, job: dict, projects: list[dict], skillset: set[str], market: dict,
                  rng: random.Random) -> dict:
    canon = [canonical_skill(s) for s in job["skills"]][:6]
    overlap = len(set(canon) & skillset) / len(canon)
    related = [p for p in projects if expand_skills(p["skills"] + p["implied_skills"]) & set(canon)]
    n_evidence = min(len(related), rng.choices([0, 1, 2], [0.25, 0.5, 0.25])[0])
    cited = rng.sample(related, n_evidence) if n_evidence else []
    opening = rng.choices(["personal", "semi", "generic"], [0.4, 0.2, 0.4])[0]
    mine = [s for s in canon if s in skillset] or canon
    parts = []
    if opening == "personal":
        parts.append(rng.choice(T.PERSONAL_OPENINGS).format(
            snippet=job_snippet(job["description"]), skill=mine[0], skill2=mine[-1] if len(mine) > 1 else mine[0]))
    elif opening == "semi":
        parts.append(rng.choice(T.SEMI_OPENINGS).format(title=job["title"]))
    else:
        parts.append(rng.choice(T.GENERIC_OPENINGS))
    for item in cited:
        implied = item["implied_skills"]
        parts.append(rng.choice(T.EVIDENCE_PARAS).format(
            short=item["short"], client_type=item["client_type"], industry=item["industry"], year=item["year"],
            metric=item["metric"], clue=clue_line(rng.choice(implied), rng) if implied else "",
            explicit=explicit_line(rng.choice(item["skills"]), T.EXPLICIT_PITCH, rng)).replace("  ", " "))
    if not cited and opening != "generic":
        parts.append("I have worked on problems close to this one and can walk you through how I would approach it.")
    long_text = rng.random() < 0.25
    if rng.random() < 0.7 or long_text:
        parts.append(rng.choice(T.PLAN_PARAS).format(skills=", ".join(mine[:3])))
    if long_text:
        parts += rng.sample(T.FILLER_LONG, 3)
    question = rng.random() < 0.45
    if question:
        parts.append(rng.choice(T.QUESTIONS))
    parts.append(rng.choice(T.CLOSINGS))
    parts.append(pdef["name"].split()[0])
    kind = job["payment_type"]
    typical = (market[kind]["p50"] or (40 if kind == "fixed" else 30))
    bid = typical * math.exp(rng.gauss(0, 0.28))
    bid = round(bid, -1) if kind == "fixed" else round(bid)
    bid = max(bid, 20 if kind == "fixed" else 8)
    outcome = draw_outcome(rng, opening, len(cited), overlap, question, bid / typical, long_text)
    when = date(2025, 2, 1) + timedelta(days=rng.randint(0, 600))
    return {
        "proposal_id": f"prop-{pdef['short']}-{number:03d}", "job_title": job["title"],
        "job_category": job["category"], "job_skills": job["skills"], "date": when.isoformat(),
        "text": "\n\n".join(parts), "bid_amount": bid, "payment_type": kind, "outcome": outcome,
        "project_ids": [project_id(pdef, p["n"]) for p in cited],
    }


def make_proposals(pdef: dict, pool: list[dict], market: dict, rng: random.Random, count: int = 150) -> list[dict]:
    skillset = persona_skillset(pdef)

    def coverage(job: dict) -> float:
        canon = {canonical_skill(s) for s in job["skills"][:6]}
        return len(canon & skillset) / len(canon)

    near = [j for j in pool if coverage(j) >= 0.5]
    far = [j for j in pool if 0 < coverage(j) < 0.5]
    chosen = rng.sample(near, int(count * 0.75)) + rng.sample(far, count - int(count * 0.75))
    rng.shuffle(chosen)
    return [make_proposal(pdef, i + 1, job, pdef["projects"], skillset, market, rng) for i, job in enumerate(chosen)]


# ---------------------------------------------------------------------------------------------------------
# Reviews and CV
# ---------------------------------------------------------------------------------------------------------

def make_reviews(pdef: dict, rng: random.Random) -> list[dict]:
    reviews = []
    for number in range(1, rng.randint(26, 36)):
        item = rng.choice(pdef["projects"])
        template, rating = rng.choice(T.REVIEWS)
        # the review points at the project only through its industry and outcome, never by name
        outcome_phrase = sentence(item["metric"])
        reviews.append({
            "review_id": number, "client": rng.choice(T.CLIENT_NAMES), "rating": rating,
            "date": (date(2023, 3, 1) + timedelta(days=rng.randint(0, 1200))).isoformat(),
            "text": template.format(industry=item["industry"], outcome_phrase=outcome_phrase),
            "project_ids": [project_id(pdef, item["n"])],
        })
    return reviews


def ascii_text(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


def write_cv(pdef: dict, profile: dict, path: Path) -> None:
    pdf = FPDF()
    pdf.set_creation_date(datetime(2026, 10, 27))
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, ascii_text(pdef["name"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, ascii_text(f"{pdef['headline']}\n{pdef['location']}"), new_x="LMARGIN", new_y="NEXT")

    def section(title: str, body: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, ascii_text(body), new_x="LMARGIN", new_y="NEXT")

    section("Summary", f"{pdef['summary']} {pdef['years_experience']} years of experience. "
                       f"Hourly rate from {profile['hourly_target']:.0f} USD.")
    section("Core skills", ", ".join(pdef["skills"]))
    recent = sorted(pdef["projects"], key=lambda p: -p["year"])
    lines = [f"{p['year']}  {p['name']} ({p['industry']}): {p['metric']}" for p in recent[:12]]
    section("Selected projects", "\n".join(lines))
    section("Education", pdef["education"])
    section("Working style", "Short written updates every working day, small releases and clear handover notes.")
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


# ---------------------------------------------------------------------------------------------------------
# Whole persona
# ---------------------------------------------------------------------------------------------------------

def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_persona(pdef: dict, pool: list[dict], market: dict, out_root: Path, seed: int) -> dict:
    """Write all persona files under out_root/<persona_id>. Returns a short summary."""
    rng = random.Random(f"{seed}-{pdef['persona_id']}")
    root = out_root / pdef["persona_id"]
    persona = pdef["persona_id"]
    by_number = {p["n"]: p for p in pdef["projects"]}
    profile = build_profile(pdef, market)
    write_json(root / "profile.json", profile)

    proposals = make_proposals(pdef, pool, market, rng)
    write_json(root / "proposals.json", proposals)
    write_json(root / "reviews.json", make_reviews(pdef, rng))

    repos_by_project: dict[int, list[str]] = {}
    for spec in pdef["repos"]:
        for number in spec["projects"]:
            repos_by_project.setdefault(number, []).append(spec["name"])
        for relative, text in render_repo(pdef, spec, by_number, rng).items():
            write_text(root / "repos" / spec["name"] / relative, text)

    projects_json = []
    for item in pdef["projects"]:
        pid = project_id(pdef, item["n"])
        artifacts = []
        if item["n"] not in pdef["no_case_study"]:
            write_text(root / "case_studies" / f"{case_id(pdef, item['n'])}.md", render_case_study(pdef, item, rng))
            artifacts.append(f"case_study:{case_id(pdef, item['n'])}")
        artifacts += [f"repo:{name}" for name in repos_by_project.get(item["n"], [])]
        artifacts += [f"proposal:{p['proposal_id']}" for p in proposals if pid in p["project_ids"]]
        projects_json.append({
            "project_id": pid, "name": item["name"], "industry": item["industry"], "skills": item["skills"],
            "implied_skills": item["implied_skills"], "year": item["year"], "client_type": item["client_type"],
            "outcome_metric": item["metric"], "artifacts": artifacts})
    write_json(root / "projects.json", projects_json)
    write_cv(pdef, profile, root / "cv.pdf")
    outcomes = {o: sum(1 for p in proposals if p["outcome"] == o) for o in ("won", "replied", "ignored")}
    return {"persona": persona, "projects": len(projects_json),
            "case_studies": len(list((root / "case_studies").glob("*.md"))), "repos": len(pdef["repos"]),
            "proposals": len(proposals), "outcomes": outcomes}
