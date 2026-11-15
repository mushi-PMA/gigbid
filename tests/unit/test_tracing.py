"""Trace spans: a human-approval pause is not an error; real failures are."""
from langgraph.errors import GraphInterrupt
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from common import tracing


def test_interrupt_is_a_pause_and_errors_stay_errors(monkeypatch):
    exporter, provider = InMemorySpanExporter(), TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "tracer", lambda: provider.get_tracer("test"))
    for error in (GraphInterrupt(()), ValueError("boom")):
        try:
            with tracing.span("node.test"):
                raise error
        except (GraphInterrupt, ValueError):
            pass
    paused, failed = exporter.get_finished_spans()
    assert paused.status.status_code.name == "UNSET"
    assert [e.name for e in paused.events] == ["paused for human approval"]
    assert failed.status.status_code.name == "ERROR" and [e.name for e in failed.events] == ["exception"]
