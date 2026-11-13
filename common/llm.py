"""One small client for every model call.

- Providers: `bedrock` (Converse API, bearer key from AWS_BEARER_TOKEN_BEDROCK) and `openai_compatible`
  (Ollama, vLLM, llama.cpp server, Groq, OpenRouter, Together; base URL and key from env).
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
import time
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
    prices = load_config()["models"].get("prices", {})
    pin, pout = prices.get(model, [0.0, 0.0])
    return (tin * pin + tout * pout) / 1_000_000


# ---------------------------------------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------------------------------------


def _bedrock_call(model: str, system: str, user: str, max_tokens: int, temperature: float,
                  region: str) -> tuple[str, int, int]:
    import boto3
    from botocore.config import Config

    timeout = load_config()["models"]["timeout_seconds"]
    client = _bedrock_clients.get(region)
    if client is None:
        client = boto3.client("bedrock-runtime", region_name=region,
                              config=Config(read_timeout=timeout, retries={"max_attempts": 1}))
        _bedrock_clients[region] = client
    response = client.converse(
        modelId=model,
        system=[{"text": system}] if system else [],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    parts = response["output"]["message"]["content"]
    text = "".join(p.get("text", "") for p in parts)
    usage = response.get("usage", {})
    return text, int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))


_bedrock_clients: dict[str, Any] = {}


def _openai_call(model: str, system: str, user: str, max_tokens: int, temperature: float,
                 base_url: str, api_key: str) -> tuple[str, int, int]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key or "none",
                    timeout=load_config()["models"]["timeout_seconds"], max_retries=0)
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    response = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                              temperature=temperature)
    text = response.choices[0].message.content or ""
    usage = response.usage
    return text, int(getattr(usage, "prompt_tokens", 0) or 0), int(getattr(usage, "completion_tokens", 0) or 0)


def _strip_reasoning(text: str) -> str:
    """Open reasoning models sometimes return <reasoning>/<think> blocks inside the text; drop them."""
    return re.sub(r"<(reasoning|think)>.*?</\1>", "", text, flags=re.DOTALL).strip()


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
    key = hashlib.sha256(json.dumps([model, system, user, max_tokens, temperature]).encode()).hexdigest()
    cache = _cache_path(key)
    if cache and cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        _meter(node, model, cached["input_tokens"], cached["output_tokens"], 0.0, cached=True)
        return cached["text"]

    models = [model]
    if node in CHEAP_NODES and profile.get("fallback") and profile["fallback"] != model:
        models.append(profile["fallback"])
    last_error: Exception | None = None
    for candidate in models:
        for attempt in range(config["models"]["retries"]):
            started = time.perf_counter()
            try:
                if profile["provider"] == "bedrock":
                    text, tin, tout = _bedrock_call(candidate, system, user, max_tokens, temperature,
                                                    profile.get("region", "us-east-1"))
                else:
                    text, tin, tout = _openai_call(candidate, system, user, max_tokens, temperature,
                                                   os.environ.get("OPENAI_BASE_URL", profile.get("base_url", "")),
                                                   os.environ.get("OPENAI_API_KEY", ""))
            except Exception as error:  # provider errors, throttling, timeouts
                last_error = error
                time.sleep(min(2 ** attempt + 0.5, 20))
                continue
            seconds = time.perf_counter() - started
            text = _strip_reasoning(text)
            _meter(node, candidate, tin, tout, seconds)
            if cache:
                cache.write_text(json.dumps({"text": text, "input_tokens": tin, "output_tokens": tout}),
                                 encoding="utf-8")
            return text
    raise LLMError(f"{node}: all models failed ({type(last_error).__name__}: {last_error})")


def _meter(node: str, model: str, tin: int, tout: int, seconds: float, cached: bool = False) -> None:
    usd = 0.0 if cached else price_usd(model, tin, tout)
    usage = current_usage()
    if usage is not None:
        usage.add(node, model, tin, tout, usd, seconds)
    record_llm_call(node=node, model=model, input_tokens=tin, output_tokens=tout, usd=usd, seconds=seconds,
                    cached=cached)


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
    schema_text = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    instruction = (f"{system}\n\nAnswer with one JSON object only, matching this JSON schema exactly:\n{schema_text}")
    text = complete(node, instruction, user, max_tokens=max_tokens, temperature=temperature)
    try:
        return schema.model_validate(extract_json(text))
    except (ValueError, ValidationError) as error:
        repair = (f"{user}\n\nYour previous answer was not valid ({str(error)[:300]}). "
                  "Return only the corrected JSON object.")
        text = complete(node, instruction, repair, max_tokens=max_tokens, temperature=temperature)
        return schema.model_validate(extract_json(text))
