from __future__ import annotations

from analysis.fallback_report import build_fallback_report
from analysis.report_validator import validate_report

PAYLOAD = {
    "report_date": "2026-06-08",
    "offsite": {
        "summary_by_source": {
            "slickdeals": {"deal_count": 12, "brand_count": 3, "price_min": 6.79, "price_max": 55.0},
            "hip2save": {"deal_count": 2, "brand_count": 2, "price_min": 9.0, "price_max": 89.99},
        },
        "price_range": {"lowest_price_deal": {"brand": "Gaiatop", "price": 6.79}},
    },
}


def test_fallback_has_four_sections_and_title():
    md = build_fallback_report(PAYLOAD, reason="empty output")
    assert "竞品监控日报 · 2026-06-08" in md
    for sec in ("## 一、总览", "## 二、站外每日发现", "## 三、建议", "## 四、注意"):
        assert sec in md
    assert "14 条" in md  # 12 + 2
    assert "fallback" in md.lower()


def test_fallback_passes_validator():
    md = build_fallback_report(PAYLOAD, reason="x")
    # fallback 报告本身必须通过校验（无外链、结构完整）
    assert validate_report(md, PAYLOAD).ok


def test_fallback_empty_payload():
    md = build_fallback_report({"report_date": "2026-06-08", "offsite": {}}, reason="no data")
    assert "暂无" in md
    assert validate_report(md, {"offsite": {}}).ok
