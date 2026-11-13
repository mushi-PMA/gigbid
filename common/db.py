"""Postgres helpers and the application schema (users, settings, encrypted OAuth tokens, job records, memory)."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  user_id text PRIMARY KEY, email text UNIQUE NOT NULL, password_hash text NOT NULL, display_name text NOT NULL,
  persona text NOT NULL DEFAULT 'ai_ml_engineer', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS user_settings (
  user_id text PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE, settings jsonb NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS marketplace_accounts (
  user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, provider text NOT NULL,
  secret_enc text NOT NULL, client_info_enc text, updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, provider));
CREATE TABLE IF NOT EXISTS jobs_seen (
  user_id text NOT NULL, job_id text NOT NULL, content_hash text NOT NULL,
  first_seen timestamptz NOT NULL DEFAULT now(),
  thread_id text, status text NOT NULL DEFAULT 'queued', summary jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, job_id));
CREATE INDEX IF NOT EXISTS jobs_seen_hash ON jobs_seen (user_id, content_hash);
CREATE TABLE IF NOT EXISTS pipeline_cards (
  user_id text NOT NULL, proposal_id text NOT NULL, job_id text NOT NULL, title text NOT NULL, stage text NOT NULL,
  data jsonb NOT NULL DEFAULT '{}', updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, proposal_id));
CREATE TABLE IF NOT EXISTS run_metrics (
  run_id text PRIMARY KEY, user_id text NOT NULL, kind text NOT NULL, job_id text, started_at timestamptz NOT NULL,
  seconds double precision NOT NULL, tokens integer NOT NULL, usd double precision NOT NULL, status text NOT NULL,
  trace_id text, by_node jsonb NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS conversations (
  user_id text NOT NULL, marketplace_thread text NOT NULL, graph_thread_id text NOT NULL, job_id text,
  status text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, marketplace_thread));
CREATE TABLE IF NOT EXISTS approvals_log (
  id bigserial PRIMARY KEY, user_id text NOT NULL, thread_id text NOT NULL, kind text NOT NULL, action text NOT NULL,
  reason text NOT NULL DEFAULT '', diff text NOT NULL DEFAULT '', at timestamptz NOT NULL DEFAULT now());
"""


def database_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    return url.replace("+psycopg", "") if url else None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        url = database_url()
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = ConnectionPool(url, min_size=1, max_size=10, kwargs={"autocommit": True, "row_factory": dict_row},
                               open=True)
        with _pool.connection() as conn:
            conn.execute(SCHEMA)
    return _pool


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with pool().connection() as conn:
        yield conn


def fetch_all(sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
    with connection() as conn:
        return list(conn.execute(sql, params).fetchall())


def fetch_one(sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
    with connection() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple | dict = ()) -> None:
    with connection() as conn:
        conn.execute(sql, params)
