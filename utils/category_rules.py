"""外置类目规则加载。用 3.11 标准库 tomllib 读 config/category_rules.toml；
缺失或解析失败时回退到内置默认规则，保证生产不因配置问题挂掉。"""
from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Pattern

logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "category_rules.toml"

# 内置默认规则 = 外置文件缺失时的兜底，必须与 category_rules.toml 等价。
DEFAULT_RULES: dict[str, dict[str, list[str]]] = {
    "fan": {
        "hard_exclude_patterns": [
            r"\bbullseye\b", r"\bplayground\b", r"\bblasters?\b",
            r"bubble[-\s]?fans?", r"bubble[-\s]?machine", r"dollar[-\s]?spot",
            r"\bpeeps\b", r"\bcupcakes?\b", r"\bhostess\b", r"\btwinkies?\b",
            r"\bmarshmallows?\b", r"\bgummies?\b", r"ice[-\s]?cream", r"\bpopsicles?\b",
            r"ceiling[-\s]?fans?", r"tower[-\s]?fans?", r"pedestal[-\s]?fans?",
            r"box[-\s]?fans?", r"stand(?:ing)?[-\s]?fans?", r"window[-\s]?fans?",
            r"exhaust[-\s]?fans?", r"attic[-\s]?fans?", r"whole[-\s]?house[-\s]?fans?",
            r"wall[-\s]?mount(?:ed)?[-\s]?fans?",
        ],
        "audience_patterns": [
            r"\bfans\s*[:,]",
            r"\bfans\s+(?:can|will|get|got|rejoice|unite|everywhere|listen|score|love|want|rally)\b",
        ],
        "product_modifiers": [
            "portable", "handheld", "hand-held", "hand held", "mini", "neck",
            "usb", "rechargeable", "battery", "bladeless", "clip", "clip-on",
            "personal", "waist", "pocket", "desk",
        ],
        "non_product_patterns": [
            r"fans?[-\s]?favorites?", r"fans?[-\s]?fest", r"fans?[-\s]?club",
            r"fans?[-\s]?cave", r"fans?[-\s]?gear", r"fans?[-\s]?mail", r"fan[-\s]?fiction",
            r"fans\s*:", r"for[-\s]+(?:[a-z'’\-]+[-\s]+){0,3}fans?\b",
            r"(?:soccer|football|sports?|baseball|basketball|hockey|nfl|nba|mlb|music|movie|concert|anime|k-?pop)[-\s]+fans?",
        ],
    },
    "hand_warmer": {"include_patterns": [r"\bhand[-\s]?warmers?\b"]},
}


@dataclass
class FanMatchers:
    hard_exclude: list[Pattern[str]] = field(default_factory=list)
    audience: list[Pattern[str]] = field(default_factory=list)
    non_product: list[Pattern[str]] = field(default_factory=list)
    product: Pattern[str] | None = None


def load_category_rules(path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    """读外置 TOML 并覆盖到默认规则之上；文件缺失/损坏时返回默认。"""
    path = path or RULES_PATH
    merged = {cat: dict(rules) for cat, rules in DEFAULT_RULES.items()}
    try:
        with path.open("rb") as f:
            data: dict[str, Any] = tomllib.load(f)
    except FileNotFoundError:
        logger.info("category_rules.toml not found, using built-in defaults")
        return merged
    except Exception:
        logger.exception("category_rules.toml parse failed, using built-in defaults")
        return merged
    for category, rules in data.items():
        if isinstance(rules, dict):
            merged.setdefault(category, {})
            for key, value in rules.items():
                if isinstance(value, list):
                    merged[category][key] = [str(v) for v in value]
    return merged


def _compile_fan(rules: dict[str, list[str]]) -> FanMatchers:
    modifiers = rules.get("product_modifiers") or []
    product = None
    if modifiers:
        alt = "|".join(re.escape(m) for m in modifiers)
        product = re.compile(
            rf"(?:{alt})[\w\s\-/(),.]{{0,25}}?\bfans?\b|\bfans?\b[\w\s\-/(),.]{{0,25}}?(?:{alt})"
        )
    return FanMatchers(
        hard_exclude=[re.compile(p) for p in rules.get("hard_exclude_patterns", [])],
        audience=[re.compile(p) for p in rules.get("audience_patterns", [])],
        non_product=[re.compile(p) for p in rules.get("non_product_patterns", [])],
        product=product,
    )


@lru_cache(maxsize=1)
def get_fan_matchers() -> FanMatchers:
    return _compile_fan(load_category_rules().get("fan", {}))


@lru_cache(maxsize=1)
def get_hand_warmer_matchers() -> list[Pattern[str]]:
    rules = load_category_rules().get("hand_warmer", {})
    return [re.compile(p) for p in rules.get("include_patterns", [])]
