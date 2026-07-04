from __future__ import annotations

from pathlib import Path

from scrapers.hip2save_scraper import (
    Hip2SaveLink,
    dedupe_deals,
    parse_detail_page,
)
from scrapers.slickdeals_scraper import KeywordConfig

DETAIL = (Path(__file__).parent / "fixtures" / "hip2save" / "detail_fan_sample.html").read_text(
    encoding="utf-8"
)


def test_detail_page_parses_price_and_date():
    link = Hip2SaveLink(url="https://hip2save.com/deals/diveblues-fan/", title=None)
    deal = parse_detail_page(DETAIL, link, KeywordConfig("handheld fan", "fan"), ["Diveblues"])
    assert deal is not None
    assert deal["source"] == "hip2save"
    assert deal["deal_id"].startswith("hip2save:")
    assert deal["price"] == 9.0
    assert deal["original_price"] == 19.0
    assert deal["discount_pct"] is not None and 45 <= deal["discount_pct"] <= 60
    assert deal["posted_at"].startswith("2026-06-05")
    assert deal["brand"] == "Diveblues"
    assert deal["comments_count"] == 12


def test_detail_page_rejects_irrelevant_category():
    link = Hip2SaveLink(url="https://hip2save.com/deals/ceiling-fan/", title="Hunter Ceiling Fan")
    # title overrides to a ceiling fan -> excluded by category rules
    html = DETAIL.replace(
        "Diveblues Portable Handheld Fan Just $9 on Amazon (Reg. $19)",
        "Hunter 52in Ceiling Fan",
    )
    deal = parse_detail_page(html, link, KeywordConfig("handheld fan", "fan"), ["Diveblues"])
    assert deal is None


def test_dedupe_by_deal_id():
    deals = [
        {"deal_id": "hip2save:a", "title": "x"},
        {"deal_id": "hip2save:a", "title": "x2"},
        {"deal_id": "hip2save:b", "title": "y"},
    ]
    assert len(dedupe_deals(deals)) == 2
