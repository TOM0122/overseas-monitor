from __future__ import annotations

from pathlib import Path

from utils import category_rules
from utils.category_rules import DEFAULT_RULES, load_category_rules


def test_default_rules_loaded_from_shipped_toml():
    rules = load_category_rules()
    assert "fan" in rules and "hand_warmer" in rules
    assert rules["fan"]["product_modifiers"]
    assert any("ceiling" in p for p in rules["fan"]["hard_exclude_patterns"])


def test_missing_file_falls_back_to_defaults():
    rules = load_category_rules(Path("/nonexistent/category_rules.toml"))
    assert rules == {c: dict(r) for c, r in DEFAULT_RULES.items()}


def test_broken_toml_falls_back(tmp_path):
    bad = tmp_path / "category_rules.toml"
    bad.write_text("this is = = not valid toml [[[", encoding="utf-8")
    rules = load_category_rules(bad)
    assert rules["fan"]["product_modifiers"] == DEFAULT_RULES["fan"]["product_modifiers"]


def test_shipped_toml_matches_builtin_defaults():
    # 外置 TOML 与内置默认必须等价，否则回退会改变行为
    shipped = load_category_rules()
    for category, rules in DEFAULT_RULES.items():
        for key, value in rules.items():
            assert shipped[category][key] == value, (category, key)


def test_matchers_compile_and_classify():
    category_rules.get_fan_matchers.cache_clear()
    fan_url = "https://slickdeals.net/f/1-x"
    from scrapers.slickdeals_scraper import is_relevant_to_category

    assert is_relevant_to_category("Portable Handheld Fan", fan_url, "fan") is True
    assert is_relevant_to_category("Honeywell Tower Fan", fan_url, "fan") is False
    assert is_relevant_to_category("Dunkin' Fans Can Score a FREE Donut", fan_url, "fan") is False
    assert is_relevant_to_category("Rechargeable Hand Warmer", fan_url, "hand_warmer") is True
