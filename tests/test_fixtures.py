from __future__ import annotations

from pathlib import Path

from scrapers.slickdeals_scraper import KeywordConfig, parse_search_results

FIXTURE = Path(__file__).parent / "fixtures" / "slickdeals" / "handheld_fan_search.html"


def test_parse_real_search_page():
    html = FIXTURE.read_text(encoding="utf-8")
    deals = parse_search_results(
        html=html,
        keyword_config=KeywordConfig(keyword="handheld fan", category="fan"),
        monitored_brands=["Diveblues", "Aecooly"],
        limit=50,
        max_post_age_days=3650,
    )
    assert len(deals) >= 10
    for deal in deals:
        assert isinstance(deal["deal_id"], str) and deal["deal_id"]
        assert deal["url"].startswith("https://slickdeals.net/")
        assert deal["category"] == "fan"
        assert deal["price"] is None or (isinstance(deal["price"], float) and deal["price"] >= 0)
        assert deal["discount_pct"] is None or 0 <= deal["discount_pct"] <= 100
