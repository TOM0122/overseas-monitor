from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from analysis.analyzer import build_report_payload


def test_bsr_monitor_prefers_bestseller_rank_over_snapshot_bsr():
    payload = build_report_payload(
        report_date=date(2026, 6, 2),
        tz=ZoneInfo("Asia/Shanghai"),
        slickdeals=[],
        amazon_today=[
            {
                "asin": "B0GCWDN43C",
                "brand": "Diveblues",
                "bsr": 8,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            }
        ],
        amazon_yesterday=[
            {
                "asin": "B0GCWDN43C",
                "brand": "Diveblues",
                "bsr": 9,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-01T00:00:00+00:00",
            }
        ],
        top_deals_limit=20,
        monitored_brands=["Diveblues"],
        bestsellers_today=[
            {
                "asin": "B0GCWDN43C",
                "brand": "Diveblues",
                "title": "Diveblues Fan",
                "rank": 10,
                "is_tracked": True,
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            }
        ],
        bestsellers_yesterday=[
            {
                "asin": "B0GCWDN43C",
                "brand": "Diveblues",
                "title": "Diveblues Fan",
                "rank": 8,
                "is_tracked": True,
                "snapshot_at": "2026-06-01T00:00:00+00:00",
            }
        ],
        focus_brand="Diveblues",
    )

    item = payload["bsr_monitor"]["focus"][0]
    assert item["source"] == "amazon_bestsellers"
    assert item["current_rank"] == 10
    assert item["yesterday_rank"] == 8
    assert item["rank_change_display"] == "+2 名"
