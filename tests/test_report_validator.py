from __future__ import annotations

from analysis.report_validator import validate_report

PAYLOAD = {
    "report_date": "2026-06-08",
    "offsite": {
        "slickdeals_competitor_deals": [
            {"brand": "Gaiatop", "url": "https://slickdeals.net/f/19564116-gaiatop-fan?src=x"},
        ],
    },
}

GOOD = """竞品监控日报 · 2026-06-08

## 一、总览
今日站外 3 条。

## 二、站外每日发现
| 品牌 | 折扣 |
| --- | --- |
| Gaiatop | 50% | [查看](https://slickdeals.net/f/19564116)

## 三、建议
- 跟价 Gaiatop。

## 四、注意
- 无。
"""


def test_good_report_passes():
    r = validate_report(GOOD, PAYLOAD)
    assert r.ok and not r.errors


def test_empty_report_fails():
    r = validate_report("", PAYLOAD)
    assert not r.ok


def test_missing_section_fails():
    r = validate_report(GOOD.replace("## 三、建议", "## 3 建议"), PAYLOAD)
    assert not r.ok and any("建议" in e for e in r.errors)


def test_missing_title_fails():
    r = validate_report(GOOD.replace("竞品监控日报 · 2026-06-08", "日报"), PAYLOAD)
    assert not r.ok and any("主标题" in e for e in r.errors)


def test_out_of_whitelist_url_is_error():
    bad = GOOD.replace("https://slickdeals.net/f/19564116", "https://evil.example.com/phish")
    r = validate_report(bad, PAYLOAD)
    assert not r.ok and any("payload 之外的链接" in e for e in r.errors)


def test_shortened_url_allowed():
    # 报告里把长链接截短，仍属白名单前缀，应通过
    assert validate_report(GOOD, PAYLOAD).ok


def test_forbidden_onsite_keyword_is_error():
    bad = GOOD.replace("今日站外 3 条。", "根据 Keepa 数据，BSR 上升。")
    r = validate_report(bad, PAYLOAD)
    assert not r.ok and any("Keepa" in e for e in r.errors)


def test_hallucination_phrase_is_warning():
    warn = GOOD.replace("今日站外 3 条。", "根据历史销量判断。")
    r = validate_report(warn, PAYLOAD)
    assert r.ok  # warning 不阻断
    assert any("根据历史销量" in w for w in r.warnings)
