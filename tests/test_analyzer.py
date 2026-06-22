from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from analysis.analyzer import (
    build_report_payload,
    summarize_competitor_candidates,
    summarize_offsite_deals,
    summarize_offsite_trends,
)


TZ = ZoneInfo("Asia/Shanghai")


def test_report_payload_is_offsite_only():
    payload = build_report_payload(
        report_date=date(2026, 6, 8),
        tz=TZ,
        slickdeals=[],
        offsite_week=[],
        top_deals_limit=20,
        monitored_brands=["Diveblues"],
        focus_brand="Diveblues",
    )

    assert payload["summary_counts"] == {"offsite_deals_today": 0}
    assert "offsite" in payload
    assert "trends" in payload
    assert "competitor_candidates" in payload
    removed_keys = {
        "bsr_" + "monitor",
        "amazon_" + "top" + "30_price_monitor",
        "best" + "seller_monitor",
        "bsr_" + "category",
    }
    assert removed_keys.isdisjoint(payload)


def test_offsite_price_floor_drops_cheap_deals():
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
        TZ,
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
    out = summarize_offsite_deals(deals, TZ, 20, ["Gaiatop"], 200.0)
    ids = {deal["deal_id"] for deal in out["top_deals"]}
    assert ids == {"y"}


def test_offsite_relevance_recheck_drops_stored_noise():
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
    out = summarize_offsite_deals(deals, TZ, 20, ["Gaiatop"], 200.0)
    ids = {deal["deal_id"] for deal in out["top_deals"]}
    assert "dunk" not in ids
    assert ids == {"real"}


def test_offsite_competitor_deal_splits():
    deals = [
        {
            "deal_id": "s1",
            "source": "slickdeals",
            "title": "Gaiatop Handheld Fan",
            "brand": "Gaiatop",
            "category": "fan",
            "price": 9.99,
            "discount_pct": 50.0,
            "is_frontpage": True,
            "thumbs_up": 80,
            "comments_count": 12,
            "url": "https://slickdeals.net/f/1-x",
        },
        {
            "deal_id": "s2",
            "source": "slickdeals",
            "title": "NoName Fan",
            "brand": "unknown",
            "category": "fan",
            "price": 8.0,
            "is_frontpage": False,
            "thumbs_up": 3,
            "comments_count": 0,
            "url": "https://slickdeals.net/f/2-x",
        },
        {
            "deal_id": "h1",
            "source": "hip2save",
            "title": "Diveblues Fan Post",
            "brand": "Diveblues",
            "category": "fan",
            "price": 11.0,
            "discount_pct": 40.0,
            "comments_count": 4,
            "url": "https://hip2save.com/deals/diveblues-fan/",
        },
    ]
    out = summarize_offsite_deals(deals, TZ, 20, ["Gaiatop", "Diveblues"], 200.0)
    sd = out["slickdeals_competitor_deals"]
    hp = out["hip2save_competitor_deals"]
    assert {deal["brand"] for deal in sd} == {"Gaiatop"}
    assert sd[0]["is_frontpage"] is True and sd[0]["thumbs_up"] == 80
    assert {deal["brand"] for deal in hp} == {"Diveblues"}
    assert out["summary_by_source"]["slickdeals"]["deal_count"] == 2
    assert out["summary_by_source"]["slickdeals"]["brand_count"] == 1


def test_offsite_trends_aggregate_weekly_monitored_brands():
    rows = [
        {
            "deal_id": "d1",
            "title": "Diveblues Portable Handheld Fan",
            "url": "https://slickdeals.net/f/1-x",
            "brand": "Diveblues",
            "category": "fan",
            "price": 9.99,
            "discount_pct": 40,
        },
        {
            "deal_id": "d2",
            "title": "Diveblues Rechargeable Fan",
            "url": "https://hip2save.com/deals/diveblues-fan/",
            "brand": "Diveblues",
            "category": "fan",
            "price": 8.99,
            "discount_pct": 45,
        },
        {
            "deal_id": "g1",
            "title": "Gaiatop Mini Fan",
            "url": "https://slickdeals.net/f/2-x",
            "brand": "Gaiatop",
            "category": "fan",
            "price": 7.99,
            "discount_pct": 50,
        },
        {
            "deal_id": "noise",
            "title": "Dunkin' Fans Can Score a FREE Donut",
            "url": "https://hip2save.com/deals/dunkin-free-donut/",
            "brand": "Dunkin",
            "category": "fan",
            "price": 6,
            "discount_pct": 10,
        },
    ]
    trends = summarize_offsite_trends(
        offsite_week=rows,
        monitored_brands=["Diveblues", "Gaiatop"],
        focus_brand="Diveblues",
        max_reasonable_price=200,
    )

    assert trends["window_days"] == 7
    assert trends["focus_weekly"] == {
        "brand": "Diveblues",
        "deal_count": 2,
        "min_price": 8.99,
        "max_discount": 45.0,
    }
    assert trends["competitor_weekly"] == [
        {
            "brand": "Gaiatop",
            "deal_count": 1,
            "min_price": 7.99,
            "max_discount": 50.0,
        }
    ]


def test_competitor_candidates_are_offsite_only():
    rows = [
        {
            "deal_id": "x",
            "source": "slickdeals",
            "title": "Koonie Portable Handheld Fan",
            "brand": "unknown",
            "category": "fan",
            "thumbs_up": 40,
            "comments_count": 5,
            "is_frontpage": True,
            "url": "https://slickdeals.net/f/1-x",
            "scraped_at": "2026-06-05T00:00:00+00:00",
        },
        {
            "deal_id": "y",
            "source": "hip2save",
            "title": "Koonie Rechargeable Fan",
            "brand": "Koonie",
            "category": "fan",
            "thumbs_up": None,
            "comments_count": 2,
            "is_frontpage": None,
            "url": "https://hip2save.com/deals/koonie-fan/",
            "scraped_at": "2026-06-06T00:00:00+00:00",
        },
        {
            "deal_id": "z",
            "source": "slickdeals",
            "title": "Diveblues Portable Handheld Fan",
            "brand": "Diveblues",
            "category": "fan",
            "thumbs_up": 100,
            "comments_count": 10,
            "is_frontpage": True,
            "url": "https://slickdeals.net/f/2-x",
            "scraped_at": "2026-06-06T00:00:00+00:00",
        },
    ]
    candidates = summarize_competitor_candidates(
        offsite_rows=rows,
        monitored_brands=["Diveblues"],
    )

    assert candidates == [
        {
            "brand": "Koonie",
            "seen_days": 2,
            "source_count": 2,
            "offsite_count": 2,
            "heat_score": 104,
            "sample_title": "Koonie Portable Handheld Fan",
        }
    ]
