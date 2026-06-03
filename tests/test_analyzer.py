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


def test_bsr_monitor_keeps_focus_snapshot_when_missing_from_bestseller_rows():
    payload = build_report_payload(
        report_date=date(2026, 6, 3),
        tz=ZoneInfo("Asia/Shanghai"),
        slickdeals=[],
        amazon_today=[
            {
                "asin": "B0GCWDN43C",
                "brand": "Diveblues",
                "bsr": 13,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-03T00:00:00+00:00",
            },
            {
                "asin": "B07QK9C9KT",
                "brand": "JISULIFE",
                "bsr": 1,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-03T00:00:00+00:00",
            },
        ],
        amazon_yesterday=[
            {
                "asin": "B0GCWDN43C",
                "brand": "Diveblues",
                "bsr": 10,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            },
            {
                "asin": "B07QK9C9KT",
                "brand": "JISULIFE",
                "bsr": 2,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            },
        ],
        top_deals_limit=20,
        monitored_brands=["Diveblues", "JISULIFE"],
        bestsellers_today=[
            {
                "asin": "B07QK9C9KT",
                "brand": "JISULIFE",
                "title": "JISULIFE Fan",
                "rank": 1,
                "is_tracked": True,
                "snapshot_at": "2026-06-03T00:00:00+00:00",
            }
        ],
        bestsellers_yesterday=[
            {
                "asin": "B07QK9C9KT",
                "brand": "JISULIFE",
                "title": "JISULIFE Fan",
                "rank": 2,
                "is_tracked": True,
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            }
        ],
        focus_brand="Diveblues",
    )

    focus_item = payload["bsr_monitor"]["focus"][0]
    competitor_item = payload["bsr_monitor"]["competitors"][0]
    assert focus_item["asin"] == "B0GCWDN43C"
    assert focus_item["source"] == "amazon_snapshots"
    assert focus_item["current_rank"] == 13
    assert focus_item["rank_change_display"] == "+3 名"
    assert competitor_item["source"] == "amazon_bestsellers"


def test_bsr_monitor_sorted_by_current_rank():
    payload = build_report_payload(
        report_date=date(2026, 6, 2),
        tz=ZoneInfo("Asia/Shanghai"),
        slickdeals=[],
        amazon_today=[
            {
                "asin": "B0SNAP1",
                "brand": "Gaiatop",
                "bsr": 37,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            },
            {
                "asin": "B0SNAP2",
                "brand": "Shark",
                "bsr": None,
                "bsr_category_id": "3303867011",
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            },
        ],
        amazon_yesterday=[],
        top_deals_limit=20,
        monitored_brands=["Gaiatop", "Shark", "JISULIFE"],
        bestsellers_today=[
            {
                "asin": "B0BEST1",
                "brand": "JISULIFE",
                "title": "x",
                "rank": 1,
                "is_tracked": True,
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            },
            {
                "asin": "B0BEST2",
                "brand": "Gaiatop",
                "title": "y",
                "rank": 51,
                "is_tracked": True,
                "snapshot_at": "2026-06-02T00:00:00+00:00",
            },
        ],
        bestsellers_yesterday=[],
        focus_brand="Diveblues",
    )

    ranks = [item.get("current_rank") for item in payload["bsr_monitor"]["competitors"]]
    assert ranks == [1, 37, 51, None]
