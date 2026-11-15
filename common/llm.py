"""One small client for every model call.

- Providers: `openai_compatible` (one server: Ollama, vLLM, llama.cpp; base URL and key from env) and `pool`
  (the hosted endpoints in `models.endpoints`, used in turn; one that hits a rate limit rests until it resets, so
  free tiers add up).
- The model for each node comes from agent/config.yaml, never from code.
- Every call is metered (tokens, latency, USD) into the current trace span and into a per-run meter.
- Bounded retries with backoff; cheap nodes fall back to the profile's fallback model.
- Optional disk cache (GIGBID_LLM_CACHE=dir) makes evaluation reruns free and repeatable.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from common.config import load_config, model_profile
from common.tracing import record_llm_call

T = TypeVar("T", bound=BaseModel)

CHEAP_NODES = {"scout", "analyst", "risk_assessor", "fit_matcher", "pricing", "verifier", "compliance", "intent",
               "rag_helper"}


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    seconds: float = 0.0
    by_node: dict[str, dict[str, float]] = field(default_factory=dict)

    def add(self, node: str, model: str, tin: int, tout: int, usd: float, seconds: float) -> None:
        self.calls += 1
        self.input_tokens += tin
        self.output_tokens += tout
        self.usd += usd
        self.seconds += seconds
        row = self.by_node.setdefault(node, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0,
                                              "seconds": 0.0, "model": model})
        row["calls"] += 1
        row["input_tokens"] += tin
        row["output_tokens"] += tout
        row["usd"] += usd
        row["seconds"] += seconds

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


_current_usage: contextvars.ContextVar[Usage | None] = contextvars.ContextVar("gigbid_usage", default=None)


def start_usage() -> Usage:
    usage = Usage()
    _current_usage.set(usage)
    return usage


def current_usage() -> Usage | None:
    return _current_usage.get()


def price_usd(model: str, tin: int, tout: int) -> float:
    models = load_config()["models"]
    prices = models.get("prices", {})
    sizes = {s: m for e in models.get("endpoints", []) for s, m in reversed(list(e["models"].items()))}
    model = sizes.get(model, model)                     # a pool size name ("small") prices as its weights
    weights = model.split("/")[-1].split(":")[0]       # "openai/gpt-oss-20b:free" and "gpt-oss-20b" share a price
    pin, pout = prices.get(model, prices.get(weights, [0.0, 0.0]))
    return (tin * pin + tout * pout) / 1_000_000


# ---------------------------------------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------------------------------------


def _openai_call(model: str, system: str, user: str, max_tokens: int, temperature: float,
                 base_url: str, api_key: str, extra: dict | None = None) -> tuple[str, int, int]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key or "none",
                    timeout=load_config()["models"]["timeout_seconds"], max_retries=0)
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    response = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                              temperature=temperature, extra_body=extra or None)
    text = response.choices[0].message.content or ""
    usage = response.usage
    return text, int(getattr(usage, "prompt_tokens", 0) or 0), int(getattr(usage, "completion_tokens", 0) or 0)


def _openai_tools_call(model: str, system: str, user: str, tools: list[dict[str, Any]], base_url: str,
                       api_key: str, extra: dict | None = None) -> tuple[list[dict[str, Any]], int, int]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key or "none",
                    timeout=load_config()["models"]["timeout_seconds"], max_retries=0)
    from openai import BadRequestError

    try:
        response = client.chat.completions.create(
            model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            tools=[{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                     "parameters": t["input_schema"]}} for t in tools],
            temperature=0, max_tokens=800, extra_body=extra or None)
    except BadRequestError as error:
        body = error.body if isinstance(error.body, dict) else {}
        if "tool_use_failed" in json.dumps(body) or "failed_generation" in json.dumps(body):
            return [], 0, 0        # the model wrote an invalid tool call: scored as no valid call
        raise
    message = response.choices[0].message
    calls = [{"name": c.function.name, "arguments": json.loads(c.function.arguments or "{}")}
             for c in (message.tool_calls or [])]
    return calls, int(response.usage.prompt_tokens or 0), int(response.usage.completion_tokens or 0)


def _openai_endpoint(profile: dict[str, Any]) -> tuple[str, str]:
    """Base URL and key for an OpenAI-compatible profile; the key comes from the env var named in `api_key_env`."""
    key_env = profile.get("api_key_env", "OPENAI_API_KEY")
    return os.environ.get("OPENAI_BASE_URL", profile.get("base_url", "")), os.environ.get(key_env, "")


_pool_lock = threading.Lock()
_pool_turn = 0
_pool_resting: dict[str, float] = {}       # endpoint name -> time it may be used again


def _retry_after(error: Exception) -> float:
    """Seconds to rest an endpoint after `error`: the provider's retry-after on a rate limit (at least 2 s, since
    per-minute token limits often say "try again in 100ms" and fail again at once), else a short pause."""
    response = getattr(error, "response", None)
    if getattr(error, "status_code", None) == 429 or "rate" in type(error).__name__.lower():
        try:
            return min(max(float(response.headers.get("retry-after", 30)), 2.0), 300)
        except (AttributeError, TypeError, ValueError):
            return 30.0
    return 5.0


def _bad_request(error: Exception) -> bool:
    """A 400 is about the request itself: the same request fails on every endpoint, so do not retry it."""
    return getattr(error, "status_code", None) == 400


class LanesResting(LLMError):
    """Every lane for a size rests for a while (for example a daily token limit): a caller with a fallback model
    should use it now instead of waiting."""


def _pool_call(size: str, call: Callable[[str, str, str, dict], Any], patient: bool = True) -> tuple[Any, str]:
    """Run `call(model, base_url, api_key, extra_body)` on the next endpoint that serves `size` and is not resting.
    Returns the result and the model id that answered. Waits for the first endpoint to wake when all rest, unless
    `patient` is False and the wait is long (then raises LanesResting so the caller can fall back)."""
    global _pool_turn
    models = load_config()["models"]
    # one lane per (endpoint, key, size): providers limit each key and each model separately. An api_key_env
    # variable may hold several comma-separated keys.
    lanes = [(f"{e['name']}#{i}:{size}", e, key.strip())
             for e in models["endpoints"] if size in e["models"]
             for i, key in enumerate(os.environ.get(e["api_key_env"], "").split(",")) if key.strip()]
    if not lanes:
        raise LLMError(f"no pool endpoint with a key serves '{size}' (set one of the api_key_env variables)")
    last: Exception | None = None
    deadline = time.time() + models.get("pool_wait_seconds", 600)
    while time.time() < deadline:
        with _pool_lock:
            now = time.time()
            ready = [lane for lane in lanes if _pool_resting.get(lane[0], 0) <= now]
            if ready:
                lane = ready[_pool_turn % len(ready)]
                _pool_turn += 1
            else:
                lane, wait = None, min(_pool_resting[name] for name, _, _ in lanes) - now
        if lane is None:
            if not patient and wait > models.get("fallback_after_seconds", 30):
                raise LanesResting(f"every '{size}' lane rests for {wait:.0f}s ({type(last).__name__}: {last})")
            time.sleep(max(wait, 0.5))
            continue
        name, endpoint, key = lane
        model = endpoint["models"][size]
        try:
            base_url = endpoint["base_url"].format_map(os.environ)   # e.g. an account id in the URL
            return call(model, base_url, key, endpoint.get("extra_body") or {}), model
        except Exception as error:  # rate limits, provider errors, timeouts
            if _bad_request(error):
                raise
            last = error
            with _pool_lock:
                _pool_resting[name] = time.time() + _retry_after(error)
    raise LLMError(f"pool '{size}': no endpoint answered in time ({type(last).__name__}: {last})")


def _strip_reasoning(text: str) -> str:
    """Open reasoning models sometimes return <reasoning>/<think> blocks inside the text; drop them."""
    return re.sub(r"<(reasoning|think|thought)>.*?(</\1>|$)", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------------------


def model_for(node: str) -> str:
    profile = model_profile()
    try:
        return profile["nodes"][node]
    except KeyError as error:
        raise LLMError(f"no model configured for node '{node}' in profile '{load_config()['models']['profile']}'") \
            from error


def _cache_path(key: str) -> Path | None:
    folder = os.environ.get("GIGBID_LLM_CACHE")
    if not folder:
        return None
    path = Path(folder) / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # read-through: a call already made in another cache (GIGBID_LLM_CACHE_FROM) is copied, not repeated; this is how
    # the small CI smoke cache is built from the full evaluation cache
    source = os.environ.get("GIGBID_LLM_CACHE_FROM")
    if source and not path.exists() and (Path(source) / key[:2] / f"{key}.json").exists():
        path.write_bytes((Path(source) / key[:2] / f"{key}.json").read_bytes())
    return path


_scripted: Any = None


def set_scripted_responses(handler: Any) -> None:
    """Tests only: route every call to `handler(node, system, user) -> str` instead of a provider."""
    global _scripted
    _scripted = handler


def complete(node: str, system: str, user: str, *, max_tokens: int | None = None, temperature: float = 0.0,
             model: str | None = None) -> str:
    """Call the model configured for `node` and return its text."""
    if _scripted is not None:
        text = _scripted(node, system, user)
        _meter(node, "scripted", len(system + user) // 4, len(text) // 4, 0.0, cached=True)
        return text
    profile = model_profile()
    config = load_config()
    model = model or model_for(node)
    max_tokens = max_tokens or config["models"]["max_output_tokens"]
    tag = config["models"].get("cache_tag", "")       # changes when request settings change (e.g. reasoning effort)
    key = hashlib.sha256(json.dumps([model, system, user, max_tokens, temperature, tag]).encode()).hexdigest()
    cache = _cache_path(key)
    if cache and cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        _meter(node, cached.get("model", model), cached["input_tokens"], cached["output_tokens"], 0.0, cached=True)
        return cached["text"]

    models = [model]
    if node in CHEAP_NODES and profile.get("fallback") and profile["fallback"] != model:
        models.append(profile["fallback"])
    last_error: Exception | None = None
    for position, candidate in enumerate(models):
        has_fallback = position < len(models) - 1
        for attempt in range(config["models"]["retries"]):
            started = time.perf_counter()
            try:
                if profile["provider"] == "pool":
                    (text, tin, tout), served_by = _pool_call(
                        candidate, lambda m, url, key, extra: _openai_call(m, system, user, max_tokens,
                                                                           temperature, url, key, extra),
                        patient=not has_fallback)
                else:
                    text, tin, tout = _openai_call(candidate, system, user, max_tokens, temperature,
                                                   *_openai_endpoint(profile))
            except LanesResting as error:     # e.g. the small model's daily quota is used up: fall back now
                last_error = error
                break
            except Exception as error:  # provider errors, throttling, timeouts
                last_error = error
                time.sleep(min(2 ** attempt + 0.5, 20))
                continue
            seconds = time.perf_counter() - started
            text = _strip_reasoning(text)
            _meter(node, served_by if profile["provider"] == "pool" else candidate, tin, tout, seconds)
            if cache:
                served = served_by if profile["provider"] == "pool" else candidate
                cache.write_text(json.dumps({"text": text, "input_tokens": tin, "output_tokens": tout,
                                             "model": served}), encoding="utf-8")
            return text
    raise LLMError(f"{node}: all models failed ({type(last_error).__name__}: {last_error})")


def _meter(node: str, model: str, tin: int, tout: int, seconds: float, cached: bool = False) -> None:
    # a call replayed from the evaluation cache still reports what it cost when it was made (list price)
    usd = price_usd(model, tin, tout)
    usage = current_usage()
    if usage is not None:
        usage.add(node, model, tin, tout, usd, seconds)
    record_llm_call(node=node, model=model, input_tokens=tin, output_tokens=tout, usd=usd, seconds=seconds,
                    cached=cached)


def complete_tools(node: str, system: str, user: str, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One tool-calling turn with native tool use. `tools` = [{"name", "description", "input_schema"}].
    Returns the calls the model made: [{"name", "arguments"}] (empty when it answered in text)."""
    profile = model_profile()
    model = model_for(node)
    key = hashlib.sha256(json.dumps(["tools", model, system, user, tools], sort_keys=True).encode()).hexdigest()
    cache = _cache_path(key)
    if cache and cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        _meter(node, model, cached["input_tokens"], cached["output_tokens"], 0.0, cached=True)
        return cached["calls"]
    started = time.perf_counter()
    last: Exception | None = None
    for attempt in range(load_config()["models"]["retries"]):
        try:
            if profile["provider"] == "pool":
                (calls, tin, tout), served_by = _pool_call(
                    model, lambda m, url, key, extra: _openai_tools_call(m, system, user, tools, url, key, extra))
            else:
                calls, tin, tout = _openai_tools_call(model, system, user, tools, *_openai_endpoint(profile))
            break
        except Exception as error:
            last = error
            time.sleep(min(2 ** attempt + 0.5, 20))
    else:
        raise LLMError(f"{node}: tool call failed ({last})")
    _meter(node, served_by if profile["provider"] == "pool" else model, tin, tout, time.perf_counter() - started)
    if cache:
        cache.write_text(json.dumps({"calls": calls, "input_tokens": tin, "output_tokens": tout}), encoding="utf-8")
    return calls


def extract_json(text: str) -> Any:
    """Return the first JSON object or array in `text` (models sometimes wrap JSON in prose or fences)."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON found")
    start = min(starts)
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(text[start:])
    return value


def complete_json(node: str, system: str, user: str, schema: type[T], *, max_tokens: int | None = None,
                  temperature: float = 0.0) -> T:
    """Ask for JSON matching `schema`; one repair round if the first answer does not validate."""
    from agent.prompts import load_prompt

    schema_text = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    instruction = f"{system}\n\n{load_prompt('_json_format', schema=schema_text)}"
    text = complete(node, instruction, user, max_tokens=max_tokens, temperature=temperature)
    try:
        return schema.model_validate(extract_json(text))
    except (ValueError, ValidationError) as error:
        # reasoning models spend output tokens on thinking, so a cut-off answer is the usual cause: double the room
        repair = load_prompt("_json_repair", request=user, error=str(error)[:300])
        # capped: free tiers count prompt plus max_tokens against a per-minute budget (8,000 on Groq)
        room = min(2 * (max_tokens or load_config()["models"]["max_output_tokens"]), 3600)
        text = complete(node, instruction, repair, max_tokens=room, temperature=temperature)
        return schema.model_validate(extract_json(text))
