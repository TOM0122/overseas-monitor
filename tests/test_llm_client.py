from __future__ import annotations

import pytest

import utils.llm_client as llm


class FakeResp:
    def __init__(self, payload, status=200, text="{}"):
        self._payload = payload
        self.status_code = status
        self.text = text
        self.ok = status < 400

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def _client(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "load_dotenv", lambda *a, **k: None)
    return llm.OpenAICompatibleClient(max_retries=1)


COMPLETION = {
    "model": "deepseek-v4-flash",
    "choices": [{"message": {"content": "  报告内容  "}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
}


def test_complete_returns_metadata(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp(COMPLETION))
    c = client.complete("prompt", system="sys")
    assert c.text == "报告内容"
    assert c.usage["total_tokens"] == 150
    assert c.raw_finish_reason == "stop"
    assert c.latency_seconds >= 0
    assert client.last_completion is c


def test_complete_prompt_returns_text(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp(COMPLETION))
    assert client.complete_prompt("p") == "报告内容"


def test_retry_then_success(monkeypatch):
    client = _client(monkeypatch)
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("network blip")
        return FakeResp(COMPLETION)

    monkeypatch.setattr(llm.requests, "post", flaky)
    assert client.complete("p").text == "报告内容"
    assert calls["n"] == 2


def test_all_retries_fail_raises(monkeypatch):
    client = _client(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm.requests, "post", boom)
    with pytest.raises(RuntimeError):
        client.complete("p")


def test_http_error_body_summary_does_not_leak_key(monkeypatch, caplog):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        llm.requests, "post", lambda *a, **k: FakeResp({}, status=429, text="rate limited\nretry")
    )
    with pytest.raises(RuntimeError):
        client.complete("p")
    # 日志里不应出现 api key
    assert "sk-test" not in caplog.text
