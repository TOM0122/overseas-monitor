from __future__ import annotations

from pathlib import Path

from scrapers.slickdeals_scraper import (
    KeywordConfig,
    is_relevant_to_category,
    parse_search_results,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "slickdeals" / "handheld_fan_search.html"
).read_text(encoding="utf-8")

REQUIRED_FIELDS = (
    "deal_id", "title", "brand", "price", "original_price", "discount_pct",
    "comments_count", "thumbs_up", "posted_at", "is_frontpage", "source",
)


def _parse():
    return parse_search_results(
        html=FIXTURE,
        keyword_config=KeywordConfig("handheld fan", "fan"),
        monitored_brands=["Diveblues", "Aecooly", "Gaiatop"],
        limit=50,
        max_post_age_days=3650,
    )


def test_fixture_yields_deals_with_all_fields():
    deals = _parse()
    assert len(deals) >= 10
    for d in deals:
        for field in REQUIRED_FIELDS:
            assert field in d, field
        assert d["source"] == "slickdeals"
        assert isinstance(d["deal_id"], str) and d["deal_id"]


def test_fixture_detects_frontpage():
    assert any(d.get("is_frontpage") for d in _parse())


def test_dealids_are_unique():
    deals = _parse()
    ids = [d["deal_id"] for d in deals]
    assert len(ids) == len(set(ids))


def test_category_rules_applied():
    url = "https://slickdeals.net/f/1-x"
    assert is_relevant_to_category("Portable Handheld Fan", url, "fan") is True
    assert is_relevant_to_category("Rechargeable Fan (Pink)", url, "fan") is True
    assert is_relevant_to_category("Dunkin' Fans Can Score a FREE Donut", url, "fan") is False
    assert is_relevant_to_category("Lasko Tower Fan", url, "fan") is False
