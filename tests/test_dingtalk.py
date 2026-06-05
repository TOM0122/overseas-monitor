from __future__ import annotations

from utils.dingtalk import _normalize_markdown


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
