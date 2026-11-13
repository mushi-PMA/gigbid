"""Users and sessions: scrypt password hashes, HS256 session tokens (Authorization header or httpOnly cookie)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status

from common import db

SESSION_HOURS = 24 * 7
COOKIE = "gigbid_session"
DEFAULT_SETTINGS: dict[str, Any] = {
    "autonomy": "suggest",              # suggest | auto_skip_low_fit (never auto-send)
    "weekly_connects_budget": 80,
    "timezone": "Asia/Karachi",
    "rates": {},                        # overrides persona floors: hourly_floor, fixed_floor, target_hourly_rate
    "saved_searches": [],               # [{"name", "query", "skills", "category", "every_hours"}]
    "filters": {"min_budget": 0, "payment_types": ["fixed", "hourly"]},
    "marketplace": "gigsim",
}


def _secret() -> str:
    return os.environ.get("APP_SECRET_KEY") or "development-only-app-secret-change-me-0123"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(expected, actual)
    except ValueError:
        return False


def create_user(email: str, password: str, display_name: str, persona: str) -> dict[str, Any]:
    user_id = f"u-{uuid.uuid4().hex[:10]}"
    db.execute("INSERT INTO users (user_id, email, password_hash, display_name, persona) VALUES (%s, %s, %s, %s, %s)",
               (user_id, email.lower(), hash_password(password), display_name, persona))
    db.execute("INSERT INTO user_settings (user_id, settings) VALUES (%s, %s)",
               (user_id, __import__("json").dumps(default_settings(persona))))
    return get_user(user_id)


def default_settings(persona: str) -> dict[str, Any]:
    searches = {
        "ai_ml_engineer": [{"name": "Machine learning", "query": "", "skills": ["Machine Learning"], "category": "",
                            "every_hours": 4},
                           {"name": "LLM and NLP", "query": "", "skills": ["Natural Language Processing"],
                            "category": "", "every_hours": 4}],
        "fullstack_web_dev": [{"name": "React and Node", "query": "", "skills": ["React"], "category": "",
                               "every_hours": 4},
                              {"name": "Web apps", "query": "", "skills": ["Web Development"], "category": "",
                               "every_hours": 4}],
        "data_analyst": [{"name": "Dashboards", "query": "", "skills": ["Data Visualization"], "category": "",
                          "every_hours": 4},
                         {"name": "SQL analysis", "query": "", "skills": ["SQL"], "category": "", "every_hours": 4}],
    }
    return {**DEFAULT_SETTINGS, "saved_searches": searches.get(persona, [])}


def get_user(user_id: str) -> dict[str, Any] | None:
    return db.fetch_one("SELECT user_id, email, display_name, persona FROM users WHERE user_id = %s", (user_id,))


def find_by_email(email: str) -> dict[str, Any] | None:
    return db.fetch_one("SELECT * FROM users WHERE email = %s", (email.lower(),))


def issue_session(user_id: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + SESSION_HOURS * 3600, "aud": "gigbid-web"},
                      _secret(), algorithm="HS256")


def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE)
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:]
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    try:
        claims = jwt.decode(token, _secret(), algorithms=["HS256"], audience="gigbid-web")
    except jwt.PyJWTError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired") from error
    user = get_user(claims["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


CurrentUser = Depends(current_user)


def get_settings(user_id: str) -> dict[str, Any]:
    row = db.fetch_one("SELECT settings FROM user_settings WHERE user_id = %s", (user_id,))
    return {**DEFAULT_SETTINGS, **(row["settings"] if row else {})}


def seed_reviewer() -> None:
    """Reviewer login preloaded with a persona (credentials from env, shared privately, never in the repo)."""
    email, password = os.environ.get("REVIEWER_EMAIL"), os.environ.get("REVIEWER_PASSWORD")
    if not email or not password or find_by_email(email):
        return
    create_user(email, password, "Reviewer", os.environ.get("REVIEWER_PERSONA", "ai_ml_engineer"))
