"""Append-only audit log of every MCP tool call: user, tool, arguments, result, trace id.

Rows go to Postgres (table `audit_log`, protected by a trigger that rejects UPDATE and DELETE) when DATABASE_URL is
set, and always to a JSONL file (AUDIT_LOG_PATH). Arguments and results are PII-masked before they are written.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.config import ROOT
from common.tracing import current_trace_id, mask_pii

_lock = threading.Lock()
_pg_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
  id bigserial PRIMARY KEY, at timestamptz NOT NULL DEFAULT now(), user_id text NOT NULL, server text NOT NULL,
  tool text NOT NULL, arguments jsonb NOT NULL, result jsonb NOT NULL, ok boolean NOT NULL, trace_id text NOT NULL);
CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log;
CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
"""


def _masked(value: Any) -> Any:
    if isinstance(value, str):
        return mask_pii(value)[:2000]
    if isinstance(value, dict):
        return {k: ("[secret]" if "token" in k.lower() else _masked(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_masked(v) for v in value[:50]]
    return value


def write(user_id: str, server: str, tool: str, arguments: dict[str, Any], result: Any, ok: bool) -> None:
    global _pg_ready
    row = {"at": datetime.now(timezone.utc).isoformat(), "user_id": user_id, "server": server, "tool": tool,
           "arguments": _masked(arguments), "result": _masked(result), "ok": ok, "trace_id": current_trace_id()}
    path = Path(os.environ.get("AUDIT_LOG_PATH", ROOT / "data" / "audit" / "audit.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")
    url = os.environ.get("DATABASE_URL")
    if url:
        try:
            import psycopg

            with psycopg.connect(url.replace("+psycopg", ""), autocommit=True) as conn:
                if not _pg_ready:
                    conn.execute(SCHEMA)
                    _pg_ready = True
                conn.execute("INSERT INTO audit_log (user_id, server, tool, arguments, result, ok, trace_id) "
                             "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                             (user_id, server, tool, json.dumps(row["arguments"], default=str),
                              json.dumps(row["result"], default=str), ok, row["trace_id"]))
        except Exception:  # the JSONL copy is already written; never fail the tool call on audit storage
            pass
