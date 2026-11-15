"""The endpoint pool: one lane per key and model, rate-limited lanes rest, bad requests are not retried."""
import pytest

from common import llm


class RateLimited(Exception):
    status_code = 429
    response = None


class BadRequest(Exception):
    status_code = 400


@pytest.fixture(autouse=True)
def two_groq_keys(monkeypatch):
    for name in ("GROQ_API_KEY", "NVIDIA_API_KEY", "CEREBRAS_API_KEY", "SAMBANOVA_API_KEY", "CLOUDFLARE_API_TOKEN",
                 "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "key-a, key-b")
    llm._pool_resting.clear()


def test_rate_limited_key_rests_and_next_key_answers():
    used = []

    def call(model, base_url, key, extra):
        used.append(key)
        if key == "key-a":
            raise RateLimited()
        return "ok"

    for _ in range(3):
        result, model = llm._pool_call("small", call)
        assert (result, model) == ("ok", "openai/gpt-oss-20b")
    assert used.count("key-a") == 1          # rested after its rate limit, not tried again
    assert any(name.startswith("groq#0:small") for name in llm._pool_resting)


def test_sizes_rest_separately():
    def call(model, base_url, key, extra):
        if model.endswith("-20b"):
            raise RateLimited()
        return "ok"

    with pytest.raises(llm.LLMError):
        llm.load_config()["models"]["pool_wait_seconds"] = 0     # do not wait in the test
        try:
            llm._pool_call("small", call)
        finally:
            llm.load_config()["models"]["pool_wait_seconds"] = 600
    assert llm._pool_call("large", call) == ("ok", "openai/gpt-oss-120b")


def test_bad_request_is_not_retried():
    calls = []

    def call(model, base_url, key, extra):
        calls.append(key)
        raise BadRequest()

    with pytest.raises(BadRequest):
        llm._pool_call("small", call)
    assert len(calls) == 1


def test_impatient_call_falls_back_when_every_lane_rests_long():
    import time

    for name in ("groq#0:small", "groq#1:small"):
        llm._pool_resting[name] = time.time() + 900          # e.g. a daily token limit
    started = time.time()
    with pytest.raises(llm.LanesResting):
        llm._pool_call("small", lambda *args: "never", patient=False)
    assert time.time() - started < 2                          # no waiting: the caller uses its fallback model


def test_provider_extra_settings_are_sent():
    seen = []
    llm._pool_call("small", lambda model, url, key, extra: seen.append(extra) or "ok")
    assert seen == [{"reasoning_effort": "low"}]               # gpt-oss on Groq: short hidden reasoning
