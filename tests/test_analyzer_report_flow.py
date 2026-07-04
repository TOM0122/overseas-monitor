from __future__ import annotations

import analysis.analyzer as az

GOOD = """竞品监控日报 · 2026-06-08

## 一、总览
今日站外 1 条。

## 二、站外每日发现
- Slickdeals：1 条。

## 三、建议
- 跟价。

## 四、注意
- 无。
"""

PAYLOAD = {"report_date": "2026-06-08", "offsite": {"summary_by_source": {}}}


class FakeClient:
    model = "fake-model"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def complete_prompt(self, prompt, system=None):
        self.calls += 1
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _patch(monkeypatch, client):
    monkeypatch.setattr(az, "get_llm_client", lambda: client)
    monkeypatch.setattr(az, "render_prompt", lambda payload: "PROMPT")


def test_good_report_returned_first_try(monkeypatch):
    client = FakeClient([GOOD])
    _patch(monkeypatch, client)
    out = az.generate_validated_report(PAYLOAD)
    assert out == GOOD
    assert client.calls == 1


def test_bad_then_good_retries_once(monkeypatch):
    client = FakeClient(["不合格的报告", GOOD])
    _patch(monkeypatch, client)
    out = az.generate_validated_report(PAYLOAD)
    assert out == GOOD
    assert client.calls == 2


def test_empty_output_falls_back(monkeypatch):
    client = FakeClient(["", ""])
    _patch(monkeypatch, client)
    out = az.generate_validated_report(PAYLOAD)
    assert "fallback" in out.lower()
    assert "## 一、总览" in out and "## 四、注意" in out


def test_bad_twice_falls_back(monkeypatch):
    client = FakeClient(["垃圾", "还是垃圾"])
    _patch(monkeypatch, client)
    out = az.generate_validated_report(PAYLOAD)
    assert "fallback" in out.lower()


def test_llm_exception_falls_back(monkeypatch):
    client = FakeClient([RuntimeError("boom"), RuntimeError("boom")])
    _patch(monkeypatch, client)
    out = az.generate_validated_report(PAYLOAD)
    assert "fallback" in out.lower()
