"""GigBid HTTP API (FastAPI). Run: uvicorn apps.api.main:app --port 8000

One trace id flows from the UI request (W3C traceparent) through the API, the graph, every MCP server and the
audit log.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import context as otel_context

from apps.api.auth.users import seed_reviewer
from apps.api.routers import analytics, approvals, auth, jobs, messages, runs, settings, upwork
from common import db
from common.tracing import context_from_headers, current_trace_id, setup_tracing, span


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing("api")
    if os.environ.get("DATABASE_URL"):
        db.pool()
        seed_reviewer()
    yield


app = FastAPI(title="GigBid API", version="1.0.0", lifespan=lifespan,
              description="Multi-agent freelancer copilot: job inbox, analyses, proposals with evidence, approvals, "
                          "client messages, pipeline and analytics.")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    token = otel_context.attach(context_from_headers(dict(request.headers)))
    try:
        with span(f"http {request.method} {request.url.path}", kind="CHAIN", path=request.url.path):
            response = await call_next(request)
            response.headers["X-Trace-Id"] = current_trace_id()
            return response
    finally:
        otel_context.detach(token)


for router in (auth.router, settings.router, jobs.router, approvals.router, messages.router, runs.router,
               analytics.router, upwork.router):
    app.include_router(router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"ok": True}
