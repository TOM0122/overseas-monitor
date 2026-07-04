"""Deterministic fallback report — used when the LLM fails or its output fails
validation. It never calls the LLM and never invents suggestions; it only
restates numbers already present in the payload, in the same four-section shape."""
from __future__ import annotations

from typing import Any


def build_fallback_report(payload: dict[str, Any], *, reason: str | None = None) -> str:
    report_date = payload.get("report_date") or ""
    offsite = payload.get("offsite") or {}
    by_source = offsite.get("summary_by_source") or {}
    sd = by_source.get("slickdeals") or {}
    hp = by_source.get("hip2save") or {}
    price_range = offsite.get("price_range") or {}
    lowest = price_range.get("lowest_price_deal") or {}

    total = (sd.get("deal_count") or 0) + (hp.get("deal_count") or 0)

    lines: list[str] = [f"竞品监控日报 · {report_date}", ""]

    lines.append("## 一、总览")
    if total:
        lowest_bit = ""
        if lowest.get("price") is not None:
            lowest_bit = f"，最低价 {lowest.get('brand') or '未知品牌'} ${lowest.get('price')}"
        lines.append(
            f"今日共抓取站外 Deal {total} 条，其中 Slickdeals {sd.get('deal_count') or 0} 条、"
            f"hip2save {hp.get('deal_count') or 0} 条{lowest_bit}。由于 LLM 报告生成或校验失败，以下为自动降级报告。"
        )
    else:
        lines.append("今日暂无站外 Deal 数据。由于 LLM 报告生成或校验失败，以下为自动降级报告。")
    lines.append("")

    lines.append("## 二、站外每日发现")
    lines.append(f"- Slickdeals：{_source_line(sd)}")
    lines.append(f"- hip2save：{_source_line(hp)}")
    lines.append("")

    lines.append("## 三、建议")
    lines.append("- 暂无自动建议。请人工复核今日高热度 Deal 与低价 Deal。")
    lines.append("")

    lines.append("## 四、注意")
    lines.append("- 本报告为 fallback 版本（deterministic，未经 LLM 表达）。")
    if reason:
        lines.append(f"- LLM validation error: {reason}")

    return "\n".join(lines).strip()


def _source_line(src: dict[str, Any]) -> str:
    count = src.get("deal_count") or 0
    if not count:
        return "暂无数据"
    brand_count = src.get("brand_count") or 0
    pmin, pmax = src.get("price_min"), src.get("price_max")
    if pmin is not None and pmax is not None:
        price = f"，价格区间 ${pmin}-${pmax}"
    else:
        price = ""
    return f"{count} 条，品牌数 {brand_count}{price}"
