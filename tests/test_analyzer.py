from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from analysis.analyzer import build_report_payload, summarize_offsite_deals


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


def test_offsite_price_floor_drops_cheap_deals():
    tz = ZoneInfo("Asia/Shanghai")
    deals = [
        {
            "deal_id": "a",
            "source": "hip2save",
            "title": "Target Bubble toy (from $1)",
            "brand": None,
            "category": "fan",
            "price": 1.0,
        },
        {
            "deal_id": "b",
            "source": "slickdeals",
            "title": "Gaiatop Fan",
            "brand": "Gaiatop",
            "category": "fan",
            "price": 7.99,
        },
        {
            "deal_id": "c",
            "source": "slickdeals",
            "title": "NoPrice Fan",
            "brand": "Gaiatop",
            "category": "fan",
            "price": None,
        },
    ]
    out = summarize_offsite_deals(
        deals,
        tz,
        20,
        ["Gaiatop"],
        200.0,
        min_offsite_price=3.0,
    )
    ids = {deal["deal_id"] for deal in out["top_deals"]}
    assert "a" not in ids
    assert ids == {"b", "c"}
    assert out["price_range"]["min"] == 7.99


def test_offsite_price_floor_default_is_five():
    tz = ZoneInfo("Asia/Shanghai")
    deals = [
        {
            "deal_id": "x",
            "source": "slickdeals",
            "title": "KIDEE Mini Fan",
            "brand": "KIDEE",
            "category": "fan",
            "price": 4.99,
        },
        {
            "deal_id": "y",
            "source": "slickdeals",
            "title": "Gaiatop Fan",
            "brand": "Gaiatop",
            "category": "fan",
            "price": 7.99,
        },
    ]
    out = summarize_offsite_deals(deals, tz, 20, ["Gaiatop"], 200.0)
    ids = {deal["deal_id"] for deal in out["top_deals"]}
    assert ids == {"y"}


def test_offsite_relevance_recheck_drops_stored_noise():
    tz = ZoneInfo("Asia/Shanghai")
    deals = [
        {
            "deal_id": "dunk",
            "source": "hip2save",
            "title": "Dunkin' Fans Can Score a FREE Donut on 6/5",
            "url": "https://hip2save.com/deals/dunkin-free-donut/",
            "brand": None,
            "category": "fan",
            "price": 6.0,
        },
        {
            "deal_id": "real",
            "source": "slickdeals",
            "title": "Gaiatop Portable Handheld Fan",
            "url": "https://slickdeals.net/f/1-x",
            "brand": "Gaiatop",
            "category": "fan",
            "price": 9.99,
        },
    ]
    out = summarize_offsite_deals(deals, tz, 20, ["Gaiatop"], 200.0)
    ids = {deal["deal_id"] for deal in out["top_deals"]}
    assert "dunk" not in ids
    assert ids == {"real"}


def test_offsite_competitor_deal_splits():
    tz = ZoneInfo("Asia/Shanghai")
    deals = [
        {"deal_id": "s1", "source": "slickdeals", "title": "Gaiatop Handheld Fan",
         "brand": "Gaiatop", "category": "fan", "price": 9.99, "discount_pct": 50.0,
         "is_frontpage": True, "thumbs_up": 80, "comments_count": 12,
         "url": "https://slickdeals.net/f/1-x"},
        {"deal_id": "s2", "source": "slickdeals", "title": "NoName Fan",
         "brand": "unknown", "category": "fan", "price": 8.0, "is_frontpage": False,
         "thumbs_up": 3, "comments_count": 0, "url": "https://slickdeals.net/f/2-x"},
        {"deal_id": "h1", "source": "hip2save", "title": "Diveblues Fan Post",
         "brand": "Diveblues", "category": "fan", "price": 11.0, "discount_pct": 40.0,
         "comments_count": 4, "url": "https://hip2save.com/deals/diveblues-fan/"},
    ]
    out = summarize_offsite_deals(deals, tz, 20, ["Gaiatop", "Diveblues"], 200.0)
    sd = out["slickdeals_competitor_deals"]
    hp = out["hip2save_competitor_deals"]
    assert {d["brand"] for d in sd} == {"Gaiatop"}            # 仅监控品牌进表
    assert sd[0]["is_frontpage"] is True and sd[0]["thumbs_up"] == 80
    assert {d["brand"] for d in hp} == {"Diveblues"}
    assert out["summary_by_source"]["slickdeals"]["deal_count"] == 2   # 总览含非监控计数
    assert out["summary_by_source"]["slickdeals"]["brand_count"] == 1  # 仅 Gaiatop 非 unknown
