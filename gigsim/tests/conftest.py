"""Test fixtures: a tiny seed in a temp folder, a temp database, a frozen clock and no random faults."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gigsim.app import Settings, create_app
from gigsim.store import parse

TOKEN = "tok-test"
ADMIN = "admin-secret"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN}"}


def job(job_id, posted_at, budget, payment_type="fixed", connects=5, skills=("Python", "Machine Learning"),
        history=False, kind="regular", questions=()):
    return {"job_id": job_id, "title": f"Build a churn model {job_id}",
            "description": "We need a churn prediction model on subscription data using Python and scikit-learn.",
            "skills": list(skills), "category": "AI & Machine Learning", "payment_type": payment_type,
            "budget_min": budget, "budget_max": budget, "experience_level": "intermediate", "connects_cost": connects,
            "client_id": "cl-1", "posted_at": posted_at, "applicants": "Less than 5",
            "screening_questions": list(questions), "url": f"https://gigsim.local/jobs/{job_id}",
            "source": "synthetic", "kind": kind, "duplicate_of": None, "history": history}


def write_seed(folder: Path) -> None:
    jobs = [
        job("j-cheap", "2026-10-27T01:00:00Z", 500, connects=5),
        job("j-premium", "2026-10-27T02:00:00Z", 2000, connects=6),
        job("j-hourly", "2026-10-27T03:00:00Z", 60, payment_type="hourly", connects=4),
        job("j-future", "2026-11-20T00:00:00Z", 300, connects=3),
        job("j-extra", "2026-10-27T04:00:00Z", 400, connects=5, skills=("React",)),
        job("j-questions", "2026-10-27T05:00:00Z", 700, connects=2, questions=["Which tools do you use?"]),
    ]
    history = [job("h-1", "2023-02-10T00:00:00Z", 450, history=True)]
    (folder / "jobs.jsonl").write_text("".join(json.dumps(j) + "\n" for j in jobs), encoding="utf-8")
    (folder / "historical_jobs.jsonl").write_text("".join(json.dumps(j) + "\n" for j in history), encoding="utf-8")
    client = {"client_id": "cl-1",
              "public": {"client_id": "cl-1", "country": "Germany", "payment_verified": True, "total_spent": 5000.0,
                         "hires": 8, "jobs_posted": 12, "rating": 4.9, "reviews_count": 8, "member_since": "2020-05",
                         "recent_feedback": ["Clear instructions."]},
              "hidden": {"must_have_skills": ["Python"], "budget_ceiling": 800.0, "dislikes_generic_openings": True,
                         "wants_screening_answers": True, "responsiveness": "fast"}}
    (folder / "clients.json").write_text(json.dumps([client]), encoding="utf-8")
    account = {"account_id": "acct-test", "persona_id": "test", "token": TOKEN, "env_token": "GIGSIM_TOKEN_TEST",
               "initial_connects": 12}
    (folder / "accounts.json").write_text(json.dumps([account]), encoding="utf-8")
    band = {"n": 100, "fixed": {"n": 60, "p25": 200, "p50": 500, "p75": 1000},
            "hourly": {"n": 40, "p25": 20, "p50": 35, "p75": 60}}
    pricing = {"all": band, "categories": {"AI & Machine Learning": band},
               "skills": {"Python": {**band, "n": 80}, "React": {**band, "n": 10}}, "personas": {}}
    (folder / "pricing.json").write_text(json.dumps(pricing), encoding="utf-8")


def make_client(tmp_path: Path, **overrides) -> TestClient:
    seed = tmp_path / "seed"
    seed.mkdir(parents=True, exist_ok=True)
    write_seed(seed)
    values = dict(db_path=str(tmp_path / "test.db"), seed_dir=seed, error_rate=0.0, rate_limit=1000,
                  start=parse("2026-10-28T00:00:00Z"), speed=0.0, admin_token=ADMIN, llm=False, seed=2026)
    values.update(overrides)
    return TestClient(create_app(Settings(**values)))


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)


def set_clock(client: TestClient, moment: str) -> None:
    response = client.post("/admin/clock", json={"now": moment}, headers=ADMIN_AUTH)
    assert response.status_code == 200


GOOD_LETTER = ("You need a churn prediction model on subscription data. I built a churn model with Python and "
               "scikit-learn for a media company and it found 61% of churners in the top decile.")


def draft(client: TestClient, job_id: str, letter: str = GOOD_LETTER, bid: float = 400, key: str | None = None,
          answers=None) -> dict:
    headers = dict(AUTH)
    if key:
        headers["Idempotency-Key"] = key
    body = {"job_id": job_id, "cover_letter": letter, "bid_amount": bid, "screening_answers": answers or []}
    response = client.post("/v1/proposals", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
