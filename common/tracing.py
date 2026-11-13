"""Tracing: OpenTelemetry spans exported to Arize Phoenix (self-hosted), one trace id from UI request to audit log.

- `PHOENIX_COLLECTOR_ENDPOINT` (e.g. http://phoenix:6006/v1/traces) turns export on; without it spans stay local.
- Spans use OpenInference attribute names, so Phoenix shows token counts and cost per node.
- `trace_id_header()` gives the W3C `traceparent` value to pass to MCP servers and GigSim.
- PII (emails, phone numbers, card-like numbers) is masked before any text is attached to a span.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")


def mask_pii(text: str) -> str:
    """Mask emails, card-like numbers, IBANs and phone numbers (order matters: cards before phones)."""
    if not text:
        return text
    text = EMAIL.sub("[email]", text)
    text = CARD.sub("[card]", text)
    text = IBAN.sub("[iban]", text)
    return PHONE.sub("[phone]", text)


def setup_tracing(service_name: str) -> None:
    global _configured
    if _configured:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name,
                                                        "openinference.project.name": "gigbid"}))
    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _configured = True


def tracer() -> trace.Tracer:
    return trace.get_tracer("gigbid")


@contextmanager
def span(name: str, kind: str = "CHAIN", **attributes: Any) -> Iterator[trace.Span]:
    with tracer().start_as_current_span(name) as current:
        current.set_attribute("openinference.span.kind", kind)
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, mask_pii(value) if isinstance(value, str) else value)
        yield current


def record_llm_call(*, node: str, model: str, input_tokens: int, output_tokens: int, usd: float, seconds: float,
                    cached: bool) -> None:
    with tracer().start_as_current_span(f"llm.{node}") as current:
        current.set_attribute("openinference.span.kind", "LLM")
        current.set_attribute("llm.model_name", model)
        current.set_attribute("llm.token_count.prompt", input_tokens)
        current.set_attribute("llm.token_count.completion", output_tokens)
        current.set_attribute("llm.token_count.total", input_tokens + output_tokens)
        current.set_attribute("llm.cost.total", usd)
        current.set_attribute("gigbid.node", node)
        current.set_attribute("gigbid.latency_seconds", seconds)
        current.set_attribute("gigbid.cached", cached)


def current_trace_id() -> str:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else ""


def trace_headers() -> dict[str, str]:
    """W3C trace context headers for outgoing calls (MCP servers, GigSim)."""
    headers: dict[str, str] = {}
    inject(headers)
    return headers


def context_from_headers(headers: dict[str, str]) -> Any:
    return extract(headers)
