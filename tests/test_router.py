import json

from sorena import router
from sorena.ratelimit import RateLimiter


class FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5


class FakeMessage:
    content = "mocked reply"


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]
    usage = FakeUsage()


def _reset_rate_limiter():
    router._rate_limiter = RateLimiter(router.RATE_LIMITS_RPM)


def test_fallback_triggers_on_failure(monkeypatch):
    _reset_rate_limiter()
    calls = []

    def fake_completion(model, messages, **kwargs):
        calls.append(model)
        if model == router.PROVIDER_CHAIN[0]:
            raise RuntimeError("simulated provider outage")
        return FakeResponse()

    monkeypatch.setattr(router.litellm, "completion", fake_completion)
    result = router.chat([{"role": "user", "content": "hi"}])

    assert result == "mocked reply"
    assert calls == router.PROVIDER_CHAIN[:2]


def test_rate_limit_blocks_before_exhaustion(monkeypatch):
    router._rate_limiter = RateLimiter({router.PROVIDER_CHAIN[0]: 1, router.PROVIDER_CHAIN[1]: 10})
    calls = []

    def fake_completion(model, messages, **kwargs):
        calls.append(model)
        return FakeResponse()

    monkeypatch.setattr(router.litellm, "completion", fake_completion)

    router.chat([{"role": "user", "content": "hi"}])  # uses up the limit=1 slot
    calls.clear()
    router.chat([{"role": "user", "content": "hi"}])  # should skip straight to provider 2

    assert calls == [router.PROVIDER_CHAIN[1]]


def test_telemetry_recorded_per_call(monkeypatch, tmp_path):
    _reset_rate_limiter()
    log_path = tmp_path / "telemetry.jsonl"
    monkeypatch.setattr("sorena.telemetry.LOG_PATH", log_path)

    def fake_completion(model, messages, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(router.litellm, "completion", fake_completion)
    monkeypatch.setattr(router.litellm, "completion_cost", lambda completion_response: 0.001)

    router.chat([{"role": "user", "content": "hi"}])

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["tokens_in"] == 10
    assert record["tokens_out"] == 5
    assert record["provider"] == router.PROVIDER_CHAIN[0].split("/")[0]
