"""Node plumbing: metering, budgets, tracing and failure handling shared by every node.

`@node("name")` wraps a node so that:
- its LLM tokens and cost are added to the thread (state `tokens`, `usd`) and its step to `steps`;
- a trace entry (node, seconds, tokens, outcome) is appended to the execution trace;
- an unavailable MCP server moves the thread to `needs_attention` with `marketplace_unavailable` (degraded mode;
  the worker re-queues it), and any other error after LangGraph's per-node retries moves it to `dead_letter`.
"""
from __future__ import annotations

import asyncio
import functools
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphBubbleUp

from agent.mcp_client import AgentTools, ServerUnavailable
from common.config import ROOT, load_config
from common.llm import LLMError, Usage, _current_usage
from common.tracing import span

NodeFn = Callable[[dict, RunnableConfig], Awaitable[dict]]
NODE_ATTEMPTS = 2  # per-node retry on unexpected errors (model and tool calls also retry inside their clients)


def ctx(config: RunnableConfig) -> dict[str, Any]:
    return config.get("configurable", {})


def tools_for(agent: str, config: RunnableConfig) -> AgentTools:
    c = ctx(config)
    factory = c.get("tools_factory")
    if factory is not None:  # tests and the in-memory harness inject their own MCP sessions
        return factory(agent, c["user_id"], c["persona"])
    return AgentTools(agent, c["user_id"], c["persona"])


def persona_profile(persona: str) -> dict[str, Any]:
    path = ROOT / "data" / "personas" / persona / "profile.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def over_budget(state: dict) -> str | None:
    budgets = load_config()["budgets"]
    if state.get("steps", 0) > budgets["max_graph_steps"]:
        return f"step budget exceeded ({state['steps']} > {budgets['max_graph_steps']})"
    if state.get("tokens", 0) > budgets["max_tokens_per_job"]:
        return f"token budget exceeded ({state['tokens']} > {budgets['max_tokens_per_job']})"
    return None


def node(name: str) -> Callable[[NodeFn], NodeFn]:
    def wrap(fn: NodeFn) -> NodeFn:
        @functools.wraps(fn)
        async def run(state: dict, config: RunnableConfig) -> dict:
            usage = Usage()
            token = _current_usage.set(usage)
            started = time.perf_counter()
            outcome = "ok"
            timeout = load_config()["budgets"].get("node_timeout_seconds", 240)
            try:
                with span(f"node.{name}", kind="AGENT", node=name):
                    for attempt in range(NODE_ATTEMPTS):
                        try:
                            update = await asyncio.wait_for(fn(state, config), timeout) or {}
                            break
                        except (GraphBubbleUp, ServerUnavailable):
                            raise
                        except Exception:
                            if attempt == NODE_ATTEMPTS - 1:
                                raise
                            await asyncio.sleep(1.5 * (attempt + 1))
            except GraphBubbleUp:  # interrupt(): the graph pauses here for a human
                _current_usage.reset(token)
                raise
            except ServerUnavailable as error:
                outcome = "degraded"
                update = {"status": "needs_attention", "status_reason": f"marketplace_unavailable: {error}",
                          "errors": [f"{name}: {error}"]}
            except (LLMError, Exception) as error:  # after the node's RetryPolicy is exhausted
                outcome = "error"
                update = {"status": "dead_letter", "status_reason": f"{name} failed: {type(error).__name__}",
                          "errors": [f"{name}: {type(error).__name__}: {str(error)[:400]}"]}
            _current_usage.reset(token)
            seconds = round(time.perf_counter() - started, 3)
            update["steps"] = 1
            update["tokens"] = usage.total_tokens
            update["usd"] = usage.usd
            update["trace"] = [{"node": name, "seconds": seconds, "tokens": usage.total_tokens,
                                "usd": round(usage.usd, 6), "outcome": outcome, "by_model": usage.by_node}]
            return update

        return run

    return wrap


def is_stopped(state: dict) -> bool:
    return state.get("status") in {"needs_attention", "dead_letter", "skipped", "blocked", "rejected", "watching"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
