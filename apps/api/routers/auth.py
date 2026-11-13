"""Sign up, sign in, sign out, current user."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from apps.api.auth.users import (COOKIE, SESSION_HOURS, CurrentUser, create_user, find_by_email, issue_session,
                                 verify_password)
from apps.api.schemas.models import LoginIn, RegisterIn, SessionOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session(response: Response, user: dict) -> SessionOut:
    token = issue_session(user["user_id"])
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_HOURS * 3600,
                        secure=False)
    return SessionOut(user=UserOut(**{k: user[k] for k in ("user_id", "email", "display_name", "persona")}),
                      token=token)


@router.post("/register", response_model=SessionOut, status_code=201)
def register(body: RegisterIn, response: Response) -> SessionOut:
    if find_by_email(body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "an account with this email already exists")
    return _session(response, create_user(body.email, body.password, body.display_name, body.persona))


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, response: Response) -> SessionOut:
    user = find_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong email or password")
    return _session(response, user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE)


@router.get("/me", response_model=UserOut)
def me(user: dict = CurrentUser) -> UserOut:
    return UserOut(**user)
