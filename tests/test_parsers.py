from __future__ import annotations

import scrapers.hip2save_scraper as h
import scrapers.keepa_fetcher as k
import scrapers.slickdeals_scraper as s
from utils.validation import sanitize_rows


def test_parse_money():
    assert s.parse_money("Deal $16.50 free ship") == 16.5
    assert s.parse_money("no price here") is None


def test_parse_discount_pct():
    assert s.parse_discount_pct("save 35% off") == 35.0


def test_extract_thread_id_from_url():
    assert s.extract_thread_id_from_url("/f/19550922-some-fan-deal?src=x") == "19550922"


def test_is_relevant_to_category():
    url = "https://slickdeals.net/f/1-x"
    assert s.is_relevant_to_category("Diveblues Portable Handheld Fan", url, "fan") is True
    assert s.is_relevant_to_category("Manchester United Soccer Fans Gift", url, "fan") is False


def test_fan_category_excludes_toy_roundup():
    assert (
        s.is_relevant_to_category(
            "Target Bullseye Playground Finds: Bubble Fans, Blasters & More",
            "https://hip2save.com/deals/target-bullseyes-playground-kids/",
            "fan",
        )
        is False
    )
    assert (
        s.is_relevant_to_category(
            "Gaiatop Portable Handheld Fan",
            "https://slickdeals.net/f/1-x",
            "fan",
        )
        is True
    )


def test_fan_category_excludes_food_roundup():
    assert (
        s.is_relevant_to_category(
            "Peeps Fans, Get Ready: Hostess Peeps Cupcakes Are Coming Soon!",
            "https://hip2save.com/deals/peeps-cupcakes/",
            "fan",
        )
        is False
    )
    assert (
        s.is_relevant_to_category(
            "Handheld Mini Fan (Candy Pink)",
            "https://slickdeals.net/f/1-x",
            "fan",
        )
        is True
    )


def test_fan_category_audience_and_type_filtering():
    fan_url = "https://slickdeals.net/f/1-x"
    negatives = [
        "Dunkin' Fans Can Score a FREE Donut on 6/5",
        "Marvel Fans Will Love This LEGO Set",
        "Starbucks Fans Rejoice: New Cups Are Here",
        "Manchester United Soccer Fans Gift Set",
        "Peeps Fans, Get Ready: Hostess Peeps Cupcakes",
        "Home Depot Deals: Up to 50% Off Ceiling Fans, Lighting & More",
        'Lasko 18" Oscillating Pedestal Fan',
        "Honeywell QuietSet Tower Fan",
        'Lasko 20" Box Fan (3-Speed)',
    ]
    for title in negatives:
        assert s.is_relevant_to_category(title, fan_url, "fan") is False, title

    positives = [
        "Gaiatop 4000mAh Rechargeable Handheld Personal Fan",
        "Diveblues Portable Handheld Fan (Black)",
        "Handheld Mini Fan (Candy Pink)",
        "Rechargeable Portable Fans Only $4.99",
        "Portable Neck Fan, USB Rechargeable",
        "USB Mini Desk Fan for Office",
        "Diveblues's Fan Now on Sale",
        "Aecooly's Fan $9.99",
    ]
    for title in positives:
        assert s.is_relevant_to_category(title, fan_url, "fan") is True, title


def test_hip2save_price_from_title():
    assert h.price_from_title("Gaiatop Fan $7.19 (Reg. $14)") == 7.19


def test_hip2save_stable_slug():
    assert h.stable_slug("https://hip2save.com/deals/diveblues-fan/") == "diveblues-fan"


def test_hip2save_match_brand_slug_fallback():
    assert (
        h.match_monitored_brand(
            "Portable Handheld Fan",
            ["Diveblues"],
            url="https://hip2save.com/deals/diveblues-fan/",
        )
        == "Diveblues"
    )
    assert h.match_monitored_brand("Diveblues Fan", ["Diveblues"]) == "Diveblues"
    assert h.match_monitored_brand("Generic Fan", ["Diveblues"]) is None


def test_hip2save_discount_prefers_computed():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<div>extra 35% off sitewide</div>", "lxml")
    assert h.extract_discount_pct(soup, "extra 35% off sitewide", 10.0, 21.0) == 52.38

    soup2 = BeautifulSoup("<div>save 35%</div>", "lxml")
    assert h.extract_discount_pct(soup2, "save 35%", None, None) == 35.0


def test_keepa_first_number_and_normalize():
    assert k.normalize_keepa_value(("2026-01-01", 16.5)) == 16.5
    assert k.first_number(float("nan")) is None
    assert k.first_number(-3) is None
    assert k.first_number(("t", 16.5)) == 16.5


def test_keepa_latest_rank_from_history():
    assert k.latest_rank_from_history([100, 5, 200, 12, 300, 8]) == 8


def test_keepa_clean_text():
    assert k.clean_text("  hi ") == "hi"
    assert k.clean_text(None) is None
    assert k.clean_text("") is None


def test_sanitize_rows_drops_and_nulls():
    rows = sanitize_rows(
        "t",
        [{"deal_id": "1", "price": -5, "discount_pct": 150}, {"price": 9}],
        ["deal_id"],
    )
    assert rows == [{"deal_id": "1", "price": None, "discount_pct": None}]
