"""Platform policy versions and the checks that submit enforces.

v1 applies before 2026-11-02T00:00:00Z, v2 from then on.
v2 adds a Connects surcharge for premium jobs and the rule `no_external_links`.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

V2_START = datetime(2026, 11, 2, tzinfo=timezone.utc)
V1_START = datetime(2026, 10, 27, tzinfo=timezone.utc)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d")
URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)

PREMIUM_FIXED_BUDGET = 1000
PREMIUM_HOURLY_BUDGET = 50
PREMIUM_SURCHARGE = 4

RULES_V1 = [
    {"id": "off_platform", "text": "No emails or phone numbers in proposals or answers. Keep contact and payment on the platform."},
    {"id": "no_fabrication", "text": "Do not claim experience or results you cannot support."},
    {"id": "no_guarantees", "text": "Do not guarantee outcomes."},
    {"id": "no_free_work", "text": "Do not offer or accept unpaid work disguised as a test."},
]
RULE_NO_LINKS = {"id": "no_external_links",
                 "text": "Cover letters and screening answers must not contain URLs (http, https or www)."}


def version_at(now: datetime) -> str:
    return "v2" if now >= V2_START else "v1"


def policy_document(now: datetime) -> dict:
    """What GET /v1/policy returns at the simulated time `now`."""
    if version_at(now) == "v1":
        return {"version": "v1", "effective_from": V1_START.strftime("%Y-%m-%dT%H:%M:%SZ"), "rules": RULES_V1,
                "connects": {"base": "the job's listed Connects cost", "surcharges": []}}
    return {
        "version": "v2", "effective_from": V2_START.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rules": RULES_V1 + [RULE_NO_LINKS],
        "connects": {"base": "the job's listed Connects cost",
                     "surcharges": [{"id": "premium_job", "connects": PREMIUM_SURCHARGE,
                                     "when": f"fixed budget_max >= {PREMIUM_FIXED_BUDGET} or "
                                             f"hourly budget_max >= {PREMIUM_HOURLY_BUDGET}"}]},
    }


def connects_cost(job: dict, now: datetime) -> int:
    cost = int(job.get("connects_cost") or 0)
    if version_at(now) == "v2" and job.get("budget_max") is not None:
        limit = PREMIUM_HOURLY_BUDGET if job["payment_type"] == "hourly" else PREMIUM_FIXED_BUDGET
        if job["budget_max"] >= limit:
            cost += PREMIUM_SURCHARGE
    return cost


def _phone_matches(text: str) -> list[str]:
    # dates and short numbers are not phone numbers: require at least nine digits
    return [m.group(0).strip() for m in PHONE_RE.finditer(text) if sum(c.isdigit() for c in m.group(0)) >= 9]


def violations(cover_letter: str, answers: list[dict], now: datetime) -> list[dict]:
    """Rule violations of a proposal under the policy in force at `now`."""
    found = []
    parts = [("cover_letter", cover_letter)] + [(f"answer {i + 1}", a.get("answer", "")) for i, a in enumerate(answers)]
    for where, text in parts:
        for match in EMAIL_RE.findall(text) + _phone_matches(text):
            found.append({"rule_id": "off_platform", "where": where, "match": match,
                          "text": "Emails and phone numbers are not allowed."})
        if version_at(now) == "v2":
            for match in URL_RE.findall(text):
                found.append({"rule_id": "no_external_links", "where": where, "match": match,
                              "text": "URLs are not allowed in cover letters or answers."})
    return found
