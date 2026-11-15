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

    def call(model, base_url, key):
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
    def call(model, base_url, key):
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

    def call(model, base_url, key):
        calls.append(key)
        raise BadRequest()

    with pytest.raises(BadRequest):
        llm._pool_call("small", call)
    assert len(calls) == 1
