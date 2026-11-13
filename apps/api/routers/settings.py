"""Onboarding and settings: persona, rates, filters, saved searches, Connects budget, autonomy, connected accounts,
portfolio upload (incremental re-index)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from apps.api.auth.users import CurrentUser, get_settings
from apps.api.schemas.models import SettingsModel
from common import db
from common.config import ROOT
from common.security import encrypt

router = APIRouter(prefix="/api", tags=["settings"])
UPLOAD_TYPES = {".md": "case_studies", ".pdf": "cv", ".json": "data", ".txt": "case_studies"}


@router.get("/settings", response_model=SettingsModel)
def read_settings(user: dict = CurrentUser) -> SettingsModel:
    settings = get_settings(user["user_id"])
    return SettingsModel.model_validate({**settings, "persona": user["persona"]})


@router.put("/settings", response_model=SettingsModel)
def write_settings(body: SettingsModel, user: dict = CurrentUser) -> SettingsModel:
    current = get_settings(user["user_id"])
    merged = {**current, **body.model_dump(exclude={"persona"})}
    db.execute("UPDATE user_settings SET settings = %s WHERE user_id = %s", (json.dumps(merged), user["user_id"]))
    if body.persona and body.persona != user["persona"]:
        db.execute("UPDATE users SET persona = %s WHERE user_id = %s", (body.persona, user["user_id"]))
    return SettingsModel.model_validate({**merged, "persona": body.persona or user["persona"]})


@router.post("/integrations/gigsim", status_code=204)
def connect_gigsim(token: str, user: dict = CurrentUser) -> None:
    """Store a GigSim account token (encrypted at rest)."""
    if not re.fullmatch(r"[A-Za-z0-9_\-.]{16,200}", token):
        raise HTTPException(422, "that does not look like a GigSim token")
    db.execute("INSERT INTO marketplace_accounts (user_id, provider, secret_enc) VALUES (%s, 'gigsim', %s) "
               "ON CONFLICT (user_id, provider) DO UPDATE SET secret_enc = EXCLUDED.secret_enc, updated_at = now()",
               (user["user_id"], encrypt(token)))


@router.get("/integrations")
def integrations(user: dict = CurrentUser) -> dict:
    rows = db.fetch_all("SELECT provider, updated_at FROM marketplace_accounts WHERE user_id = %s",
                        (user["user_id"],))
    connected = {r["provider"]: r["updated_at"].isoformat() for r in rows}
    return {"gigsim": {"connected": True, "account": "persona account" if "gigsim" not in connected else "own token"},
            "upwork": {"connected": "upwork" in connected, "since": connected.get("upwork")}}


@router.post("/portfolio/upload")
async def upload_portfolio(files: list[UploadFile] = File(...), user: dict = CurrentUser) -> dict:
    """Add work to the user's portfolio; only changed documents are re-embedded."""
    from rag.index.store import build_index
    from rag.ingest.loaders import load_persona
    from rag.retriever import get_index, invalidate

    persona_dir = ROOT / "data" / "personas" / user["persona"]
    saved = []
    for upload in files[:10]:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in UPLOAD_TYPES:
            raise HTTPException(422, f"unsupported file type {suffix}; use .md, .txt or .pdf")
        content = await upload.read()
        if len(content) > 2_000_000:
            raise HTTPException(413, "file larger than 2 MB")
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(upload.filename).name)
        target = persona_dir / ("cv.pdf" if suffix == ".pdf" else f"case_studies/{name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        saved.append(target.name)
    previous = get_index(user["persona"])
    index = build_index(user["persona"], load_persona(user["persona"]), previous=previous)
    index.save()
    invalidate(user["persona"])
    return {"saved": saved, "reindexed_documents": getattr(index, "reindexed_documents", None),
            "chunks": len(index.chunks)}
