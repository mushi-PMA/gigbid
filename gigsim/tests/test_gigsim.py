from __future__ import annotations

from gigsim import clients, policy
from gigsim.store import parse
from gigsim.tests.conftest import ADMIN_AUTH, AUTH, GOOD_LETTER, draft, make_client, set_clock

GENERIC_LETTER = "Dear Sir/Madam, I am the perfect fit for your project. Please check my profile."


def balance(client) -> int:
    return client.get("/v1/connects", headers=AUTH).json()["balance"]


# ---- auth, limits, faults ---------------------------------------------------------------------------------
def test_auth(client):
    assert client.get("/health").status_code == 200
    assert client.get("/v1/jobs").status_code == 401
    assert client.get("/v1/jobs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/v1/jobs", headers=AUTH).status_code == 200


def test_admin_needs_token(client):
    assert client.post("/admin/clock", json={"now": "2026-11-03T00:00:00Z"}).status_code == 401
    assert client.post("/admin/clock", json={"now": "2026-11-03T00:00:00Z"}, headers=ADMIN_AUTH).status_code == 200


def test_rate_limit(tmp_path):
    client = make_client(tmp_path, rate_limit=3)
    for _ in range(3):
        assert client.get("/v1/connects", headers=AUTH).status_code == 200
    blocked = client.get("/v1/connects", headers=AUTH)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_fault_injection_is_seeded(tmp_path):
    def pattern(folder):
        client = make_client(folder, error_rate=0.3)
        return [client.get("/v1/connects", headers=AUTH).status_code for _ in range(30)]

    first, second = pattern(tmp_path / "a"), pattern(tmp_path / "b")
    assert first == second
    assert 503 in first and 200 in first


# ---- reading ---------------------------------------------------------------------------------------------
def test_jobs_follow_the_clock_and_hide_labels(client):
    ids = [j["job_id"] for j in client.get("/v1/jobs", headers=AUTH).json()["jobs"]]
    assert "j-future" not in ids and "h-1" not in ids
    assert client.get("/v1/jobs/j-future", headers=AUTH).status_code == 404
    set_clock(client, "2026-11-21T00:00:00Z")
    assert client.get("/v1/jobs/j-future", headers=AUTH).status_code == 200
    one = client.get("/v1/jobs/j-cheap", headers=AUTH).json()
    assert "kind" not in one and "source" not in one and "history" not in one
    found = client.get("/v1/jobs", params={"q": "churn model", "skills": "React"}, headers=AUTH).json()
    assert [j["job_id"] for j in found["jobs"]] == ["j-extra"]


def test_client_hides_preferences(client):
    shown = client.get("/v1/clients/cl-1", headers=AUTH).json()
    assert shown["country"] == "Germany" and "hidden" not in shown and "budget_ceiling" not in shown


def test_pricing_endpoint(client):
    by_skill = client.get("/v1/market/pricing", params={"skills": "python,React"}, headers=AUTH).json()
    assert by_skill["basis"] == "skills" and by_skill["n"] == 80 and by_skill["fixed"]["p50"] == 500
    by_category = client.get("/v1/market/pricing", params={"category": "AI & Machine Learning"}, headers=AUTH).json()
    assert by_category["basis"] == "category" and by_category["hourly"]["p75"] == 60
    assert client.get("/v1/market/pricing", headers=AUTH).json()["basis"] == "all"


# ---- proposals, Connects, idempotency, dry run ------------------------------------------------------------
def test_connects_spend_on_submit(client):
    assert balance(client) == 12
    proposal = draft(client, "j-cheap")
    assert balance(client) == 12  # a draft is free
    submitted = client.post(f"/v1/proposals/{proposal['proposal_id']}/submit", json={}, headers=AUTH)
    assert submitted.status_code == 200 and submitted.json()["connects_spent"] == 5
    assert balance(client) == 7
    assert client.get("/v1/connects", headers=AUTH).json()["weekly_budget_left"] is None  # test persona has no budget


def test_not_enough_connects_is_402(client):
    for job_id in ("j-premium", "j-hourly"):  # 6 + 4 = 10 of 12 Connects
        proposal = draft(client, job_id)
        assert client.post(f"/v1/proposals/{proposal['proposal_id']}/submit", json={}, headers=AUTH).status_code == 200
    last = draft(client, "j-cheap")
    refused = client.post(f"/v1/proposals/{last['proposal_id']}/submit", json={}, headers=AUTH)
    assert refused.status_code == 402 and refused.json()["needed"] == 5
    assert balance(client) == 2


def test_idempotency_never_charges_twice(client):
    first = draft(client, "j-cheap", key="create-1")
    again = client.post("/v1/proposals", headers={**AUTH, "Idempotency-Key": "create-1"},
                                      json={"job_id": "j-cheap", "cover_letter": GOOD_LETTER, "bid_amount": 400,
                                            "screening_answers": []})
    assert again.status_code == 201 and again.json()["proposal_id"] == first["proposal_id"]
    assert again.headers["Idempotent-Replay"] == "true"
    assert len(client.get("/v1/proposals", headers=AUTH).json()["proposals"]) == 1

    url = f"/v1/proposals/{first['proposal_id']}/submit"
    one = client.post(url, json={}, headers={**AUTH, "Idempotency-Key": "submit-1"})
    two = client.post(url, json={}, headers={**AUTH, "Idempotency-Key": "submit-1"})
    assert one.status_code == two.status_code == 200 and one.json() == two.json()
    assert balance(client) == 12 - 5
    # a new key for an already submitted proposal is refused, still no second charge
    assert client.post(url, json={}, headers={**AUTH, "Idempotency-Key": "submit-2"}).status_code == 409
    assert balance(client) == 7
    # the same key for a different request is a client bug
    other = client.post("/v1/proposals", headers={**AUTH, "Idempotency-Key": "create-1"},
                        json={"job_id": "j-hourly", "cover_letter": "x", "bid_amount": 1})
    assert other.status_code == 409


def test_lost_answer_after_a_write_can_be_retried(tmp_path):
    client = make_client(tmp_path, error_rate=1.0)
    # every call fails; a write with a key may have been done anyway ("after" faults), and a retry must not double charge
    for _ in range(40):
        response = client.post("/v1/proposals", headers={**AUTH, "Idempotency-Key": "k"},
                               json={"job_id": "j-cheap", "cover_letter": GOOD_LETTER, "bid_amount": 400})
        assert response.status_code == 503
    calm = make_client(tmp_path, error_rate=0.0)
    listed = calm.get("/v1/proposals", headers=AUTH).json()["proposals"]
    assert len(listed) <= 1  # at most one proposal exists, however often the call was retried
    retry = calm.post("/v1/proposals", headers={**AUTH, "Idempotency-Key": "k"},
                      json={"job_id": "j-cheap", "cover_letter": GOOD_LETTER, "bid_amount": 400})
    assert retry.status_code == 201
    assert len(calm.get("/v1/proposals", headers=AUTH).json()["proposals"]) == 1


def test_dry_run_changes_nothing(client):
    preview = client.post("/v1/proposals", params={"dry_run": "true"}, headers=AUTH,
                          json={"job_id": "j-cheap", "cover_letter": GOOD_LETTER, "bid_amount": 400})
    assert preview.status_code == 200 and preview.json()["dry_run"] is True
    assert client.get("/v1/proposals", headers=AUTH).json()["proposals"] == []

    real = draft(client, "j-cheap")
    dry = client.post(f"/v1/proposals/{real['proposal_id']}/submit", params={"dry_run": "true"}, headers=AUTH, json={})
    assert dry.status_code == 200 and dry.json()["connects_cost"] == 5 and dry.json()["balance_after"] == 7
    assert balance(client) == 12
    assert client.get(f"/v1/proposals/{real['proposal_id']}", headers=AUTH).json()["status"] == "draft"
    set_clock(client, "2026-12-01T00:00:00Z")
    assert [e for e in client.get("/v1/events", headers=AUTH).json()["events"] if e["proposal_id"]] == []


# ---- policy ----------------------------------------------------------------------------------------------
def test_policy_switches_with_the_clock(client):
    set_clock(client, "2026-11-01T23:59:00Z")
    v1 = client.get("/v1/policy", headers=AUTH).json()
    assert v1["version"] == "v1" and v1["connects"]["surcharges"] == []
    assert policy.connects_cost({"connects_cost": 6, "budget_max": 2000, "payment_type": "fixed"}, parse("2026-11-01T00:00:00Z")) == 6
    set_clock(client, "2026-11-02T00:00:00Z")
    v2 = client.get("/v1/policy", headers=AUTH).json()
    assert v2["version"] == "v2" and "no_external_links" in [r["id"] for r in v2["rules"]]
    assert client.get("/health").json()["policy_version"] == "v2"

    # premium surcharge of +4 Connects (fixed budget >= 1000 or hourly budget >= 50)
    premium = draft(client, "j-premium")
    dry = client.post(f"/v1/proposals/{premium['proposal_id']}/submit", params={"dry_run": "true"}, headers=AUTH, json={})
    assert dry.json()["connects_cost"] == 10
    hourly = draft(client, "j-hourly")
    assert client.post(f"/v1/proposals/{hourly['proposal_id']}/submit", params={"dry_run": "true"}, headers=AUTH,
                       json={}).json()["connects_cost"] == 8
    cheap = draft(client, "j-cheap")
    assert client.post(f"/v1/proposals/{cheap['proposal_id']}/submit", params={"dry_run": "true"}, headers=AUTH,
                       json={}).json()["connects_cost"] == 5


def test_v1_charges_no_surcharge(client):
    premium = draft(client, "j-premium")
    submitted = client.post(f"/v1/proposals/{premium['proposal_id']}/submit", json={}, headers=AUTH)
    assert submitted.json()["connects_spent"] == 6 and submitted.json()["policy_version"] == "v1"


def test_email_and_phone_are_rejected_in_both_versions(client):
    for moment in ("2026-10-30T00:00:00Z", "2026-11-05T00:00:00Z"):
        set_clock(client, moment)
        job_id = "j-cheap" if moment.startswith("2026-10") else "j-extra"
        bad = draft(client, job_id, letter=GOOD_LETTER + " Write to me at jane.doe@example.com or call +44 7700 900123.")
        refused = client.post(f"/v1/proposals/{bad['proposal_id']}/submit", json={}, headers=AUTH)
        assert refused.status_code == 422
        rules = {v["rule_id"] for v in refused.json()["violations"]}
        assert rules == {"off_platform"}
    assert balance(client) == 12


def test_urls_are_rejected_only_from_v2(client):
    letter = GOOD_LETTER + " My work is at https://example.com/portfolio and www.example.org too."
    old = draft(client, "j-cheap", letter=letter)
    assert client.post(f"/v1/proposals/{old['proposal_id']}/submit", params={"dry_run": "true"}, headers=AUTH,
                       json={}).status_code == 200
    set_clock(client, "2026-11-03T00:00:00Z")
    refused = client.post(f"/v1/proposals/{old['proposal_id']}/submit", headers=AUTH, json={})
    assert refused.status_code == 422
    assert {v["rule_id"] for v in refused.json()["violations"]} == {"no_external_links"}
    answer = draft(client, "j-hourly", answers=[{"question": "q", "answer": "See www.example.org for samples of my work"}])
    assert client.post(f"/v1/proposals/{answer['proposal_id']}/submit", headers=AUTH, json={}).status_code == 422
    assert balance(client) == 12


def test_dates_are_not_phone_numbers():
    assert policy.violations("Delivered 2025-01-15 and again 2026-03-04.", [], parse("2026-10-30T00:00:00Z")) == []


# ---- simulated clients -----------------------------------------------------------------------------------
HIDDEN = {"must_have_skills": ["Python"], "budget_ceiling": 800.0, "dislikes_generic_openings": True,
          "wants_screening_answers": False, "responsiveness": "fast"}
JOB = {"job_id": "j", "client_id": "cl-1", "title": "Build a churn model", "payment_type": "fixed", "budget_max": 500,
       "description": "We need a churn prediction model on subscription data using Python and scikit-learn.",
       "skills": ["Python", "Machine Learning"], "screening_questions": []}


def proposal(letter, bid=400):
    return {"proposal_id": "p", "cover_letter": letter, "screening_answers": [], "bid_amount": bid,
            "payment_type": "fixed"}


def test_client_decision_is_deterministic_and_uses_preferences():
    strong, weak = proposal(GOOD_LETTER), proposal(GENERIC_LETTER)
    assert clients.decide(HIDDEN, JOB, strong) == clients.decide(HIDDEN, JOB, strong)
    assert clients.decide(HIDDEN, JOB, strong).score > clients.decide(HIDDEN, JOB, weak).score + 0.4
    assert clients.decide(HIDDEN, JOB, strong).replied and not clients.decide(HIDDEN, JOB, weak).viewed
    too_dear = clients.decide(HIDDEN, JOB, proposal(GOOD_LETTER, bid=2000))
    assert too_dear.score < clients.decide(HIDDEN, JOB, strong).score
    tolerant = {**HIDDEN, "dislikes_generic_openings": False}
    assert clients.decide(tolerant, JOB, weak).score > clients.decide(HIDDEN, JOB, weak).score


def test_events_arrive_over_simulated_time(client):
    created = draft(client, "j-cheap")
    client.post(f"/v1/proposals/{created['proposal_id']}/submit", json={}, headers=AUTH)
    assert client.get("/v1/events", params={"since": "2026-10-28T00:00:00Z"}, headers=AUTH).json()["events"] == []
    assert client.get(f"/v1/proposals/{created['proposal_id']}", headers=AUTH).json()["status"] == "submitted"
    set_clock(client, "2026-11-10T00:00:00Z")
    events = client.get("/v1/events", headers=AUTH).json()["events"]
    kinds = [e["type"] for e in events if e["proposal_id"] == created["proposal_id"]]
    assert kinds[0] == "proposal_viewed" and "client_replied" in kinds
    status = client.get(f"/v1/proposals/{created['proposal_id']}", headers=AUTH).json()
    assert status["status"] in {"replied", "interview", "hired"} and status["thread_id"]
    thread = client.get("/v1/threads", headers=AUTH).json()["threads"]
    mine = [t for t in thread if t["job_id"] == "j-cheap"]
    assert mine and mine[0]["unread"] >= 1
    messages = client.get(f"/v1/threads/{mine[0]['thread_id']}/messages", headers=AUTH).json()["messages"]
    assert messages[0]["sender"] == "client"
    assert client.get("/v1/threads", headers=AUTH).json()["threads"][0]["unread"] == 0  # reading marks as read


def test_generic_proposal_is_ignored(client):
    created = draft(client, "j-cheap", letter=GENERIC_LETTER)
    client.post(f"/v1/proposals/{created['proposal_id']}/submit", json={}, headers=AUTH)
    set_clock(client, "2026-12-01T00:00:00Z")
    events = [e for e in client.get("/v1/events", headers=AUTH).json()["events"] if e["proposal_id"] == created["proposal_id"]]
    assert events == []


def test_message_gets_a_later_answer(client):
    created = draft(client, "j-cheap")
    client.post(f"/v1/proposals/{created['proposal_id']}/submit", json={}, headers=AUTH)
    set_clock(client, "2026-11-10T00:00:00Z")
    thread_id = client.get(f"/v1/proposals/{created['proposal_id']}", headers=AUTH).json()["thread_id"]
    dry = client.post(f"/v1/threads/{thread_id}/messages", params={"dry_run": "true"}, headers=AUTH, json={"text": "Hello"})
    assert dry.status_code == 200
    before = len(client.get(f"/v1/threads/{thread_id}/messages", headers=AUTH).json()["messages"])
    sent = client.post(f"/v1/threads/{thread_id}/messages", headers={**AUTH, "Idempotency-Key": "m1"}, json={"text": "Hello"})
    assert sent.status_code == 200 and sent.json()["sender"] == "freelancer"
    set_clock(client, "2026-11-20T00:00:00Z")
    after = client.get(f"/v1/threads/{thread_id}/messages", headers=AUTH).json()["messages"]
    assert len(after) == before + 2 and after[-1]["sender"] == "client"


def test_inbound_threads_exist_for_the_account(client):
    set_clock(client, "2026-11-30T00:00:00Z")
    # the tiny seed has no profile file, so no relevant-job invites are made, but the call must still work
    assert client.get("/v1/threads", headers=AUTH).status_code == 200
