"""Signed tokens and encryption shared by the API and the MCP servers.

- Service tokens: short-lived HS256 JWTs the API mints for one user; MCP servers verify them (bearer auth).
- Approval tokens: minted only when a human approves an action in the UI. They bind the user, the action, the
  target and a hash of the exact payload, so a write tool cannot run on content the human did not approve.
- Field encryption (Fernet) for OAuth tokens at rest.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Any

import jwt
from cryptography.fernet import Fernet
from mcp.server.auth.provider import AccessToken

ALGORITHM = "HS256"


def _secret() -> str:
    secret = os.environ.get("MCP_SHARED_SECRET") or os.environ.get("APP_SECRET_KEY")
    if not secret:
        if os.environ.get("APP_ENV", "development") == "production":
            raise RuntimeError("MCP_SHARED_SECRET must be set in production")
        secret = "development-only-secret-change-me-0123456789"
    return secret


def mint_service_token(user_id: str, persona: str, scopes: list[str], ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    claims = {"sub": user_id, "persona": persona, "scope": " ".join(scopes), "iat": now, "exp": now + ttl_seconds,
              "aud": "gigbid-mcp"}
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


class ServiceTokenVerifier:
    """MCP `TokenVerifier`: accepts tokens minted by `mint_service_token`."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(token, _secret(), algorithms=[ALGORITHM], audience="gigbid-mcp")
        except jwt.PyJWTError:
            return None
        return AccessToken(token=token, client_id=claims["sub"], scopes=claims.get("scope", "").split(),
                           expires_at=claims["exp"], subject=claims["sub"], claims=claims)


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def mint_approval_token(user_id: str, action: str, target: str, payload: dict[str, Any],
                        ttl_seconds: int = 7 * 24 * 3600) -> str:
    now = int(time.time())
    claims = {"sub": user_id, "action": action, "target": target, "payload": payload_hash(payload), "iat": now,
              "exp": now + ttl_seconds, "aud": "gigbid-approval"}
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def check_approval_token(token: str, user_id: str, action: str, target: str, payload: dict[str, Any]) -> str | None:
    """Return None when the token approves exactly this action and payload, else the reason it does not."""
    try:
        claims = jwt.decode(token, _secret(), algorithms=[ALGORITHM], audience="gigbid-approval")
    except jwt.PyJWTError as error:
        return f"invalid approval token: {error}"
    if claims["sub"] != user_id:
        return "approval belongs to another user"
    if claims["action"] != action or claims["target"] != target:
        return "approval was given for a different action"
    if claims["payload"] != payload_hash(payload):
        return "content changed after approval"
    return None


def _fernet() -> Fernet:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(_secret().encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
