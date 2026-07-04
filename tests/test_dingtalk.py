from __future__ import annotations

from utils.dingtalk import DingTalkWebhookClient, _normalize_markdown, _truncate_for_dingtalk


def test_blank_line_inserted_around_tables():
    # LLM 常把表格紧贴标题/文字，钉钉需要表格前后有空行才渲染
    text = "## 标题\n| a | b |\n| --- | --- |\n| 1 | 2 |\n小结：xxx"
    out = _normalize_markdown(text)
    lines = out.splitlines()
    # 表格首行前必须是空行
    tbl_start = next(i for i, ln in enumerate(lines) if ln.startswith("| a"))
    assert lines[tbl_start - 1] == ""
    # 表格后的文字前也要有空行
    summary = next(i for i, ln in enumerate(lines) if ln.startswith("小结"))
    assert lines[summary - 1] == ""


def test_existing_table_blank_lines_preserved_not_doubled():
    # 已有正确空行的不应被破坏或加倍
    text = "段落\n\n| a |\n| --- |\n\n下一段"
    out = _normalize_markdown(text)
    assert "\n\n\n" not in out          # 没有多余空行
    assert "段落\n\n| a |" in out        # 表格前空行保留


def test_truncation_utf8_safe_and_appends_notice():
    text = "标题\n" + "内容" * 5000
    out = _truncate_for_dingtalk(text, 1000)
    assert len(out.encode("utf-8")) <= 1000
    out.encode("utf-8").decode("utf-8")  # 不会因切断多字节而报错
    assert out.endswith("已截断；完整数据见数据库）")


def _client(monkeypatch):
    monkeypatch.setenv("DINGTALK_WEBHOOK_URL", "http://x")
    monkeypatch.setattr("utils.dingtalk.load_dotenv", lambda *a, **k: None)
    return DingTalkWebhookClient(markdown_max_bytes=300)


def test_send_markdown_success_result(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "_post_classified", lambda payload: {"ok": True, "errcode": 0, "errmsg": "ok"})
    res = client.send_markdown("竞品监控日报", "## 一、总览\n内容")
    assert res["ok"] is True and res["truncated"] is False
    assert "original_bytes" in res and "final_bytes" in res


def test_send_markdown_truncates_and_reports(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "_post_classified", lambda payload: {"ok": True, "errcode": 0, "errmsg": "ok"})
    res = client.send_markdown("竞品监控日报", "标题\n" + "内容" * 500)
    assert res["truncated"] is True
    assert res["final_bytes"] <= 300 < res["original_bytes"]


def test_send_markdown_errcode_preserved(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client, "_post_classified",
        lambda payload: {"ok": False, "errcode": 310000, "errmsg": "keywords not in content"},
    )
    res = client.send_markdown("日报", "## 一、总览")
    assert res["ok"] is False and res["errcode"] == 310000 and "keywords" in res["errmsg"]
