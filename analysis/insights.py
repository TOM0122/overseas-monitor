"""Deterministic business insights computed before the LLM runs.

The LLM's job is to *express* these in fluent Chinese, not to invent analysis.
Everything here is derived only from fields already present in the payload.
"""
from __future__ import annotations

from typing import Any


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _heat(deal: dict[str, Any]) -> float:
    score = (_num(deal.get("thumbs_up")) or 0) + (_num(deal.get("comments_count")) or 0) * 2
    if deal.get("is_frontpage") is True:
        score += 50
    return score


def build_insights(payload: dict[str, Any]) -> dict[str, Any]:
    focus_brand = str(payload.get("focus_brand") or "")
    offsite = payload.get("offsite") or {}
    trends = payload.get("trends") or {}
    candidates = payload.get("competitor_candidates") or []

    sd_deals = list(offsite.get("slickdeals_competitor_deals") or [])
    hp_deals = list(offsite.get("hip2save_competitor_deals") or [])
    all_deals = sd_deals + hp_deals

    top_heat_deal = max(all_deals, key=_heat, default=None)
    lowest_price_deal = (offsite.get("price_range") or {}).get("lowest_price_deal")
    frontpage_deals = [d for d in sd_deals if d.get("is_frontpage") is True]

    focus_weekly = trends.get("focus_weekly")
    competitor_weekly = list(trends.get("competitor_weekly") or [])

    suggestions = _suggestion_candidates(
        focus_brand=focus_brand,
        focus_weekly=focus_weekly,
        competitor_weekly=competitor_weekly,
        frontpage_deals=frontpage_deals,
        candidates=candidates,
    )

    return {
        "top_heat_deal": top_heat_deal,
        "lowest_price_deal": lowest_price_deal,
        "frontpage_deals": frontpage_deals[:5],
        "focus_brand_weekly": focus_weekly,
        "competitor_weekly_top": competitor_weekly[:3],
        "new_competitor_candidates": candidates[:5],
        "suggestion_candidates": suggestions,
    }


def _suggestion_candidates(
    *,
    focus_brand: str,
    focus_weekly: dict[str, Any] | None,
    competitor_weekly: list[dict[str, Any]],
    frontpage_deals: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[str]:
    suggestions: list[str] = []

    # 规则1：竞品 7 天铺 Deal 频率高于自有品牌。
    focus_count = _num((focus_weekly or {}).get("deal_count")) or 0
    hotter = [
        c for c in competitor_weekly
        if (_num(c.get("deal_count")) or 0) > focus_count
    ]
    if hotter:
        names = "、".join(str(c.get("brand")) for c in hotter[:3])
        suggestions.append(
            f"竞品 {names} 近 7 天铺 Deal 频率高于自有品牌 {focus_brand or '（未配置）'}，建议复核是否补 Deal。"
        )

    # 规则2：竞品上了 Frontpage 且价格低于自有品牌近期最低价。
    focus_min = _num((focus_weekly or {}).get("min_price"))
    for deal in frontpage_deals:
        price = _num(deal.get("price"))
        if price is None:
            continue
        if focus_min is None or price < focus_min:
            suggestions.append(
                f"竞品 {deal.get('brand')} 已上 Frontpage 且价格 ${price} 偏低，"
                "需评估跟价或站外 Deal 补位。"
            )
            break

    # 规则3：出现新兴竞品候选。
    if candidates:
        names = "、".join(str(c.get("brand")) for c in candidates[:3])
        suggestions.append(f"出现新兴竞品候选 {names}，建议人工复核是否加入 brand_list。")

    return suggestions
