from __future__ import annotations

import argparse
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from scrapers.slickdeals_scraper import infer_brand_from_title, is_relevant_to_category
from utils.db import get_repository
from utils.dingtalk import get_dingtalk_client
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "daily_report.md"
BRAND_LIST_PATH = PROJECT_ROOT / "config" / "brand_list.txt"
GENERIC_BRAND_CANDIDATES = {
    "amazon",
    "best",
    "deal",
    "deals",
    "fan",
    "fans",
    "handheld",
    "mini",
    "portable",
    "prime",
    "rechargeable",
    "select",
    "usb",
}


def run(
    *,
    report_date: date | None = None,
    dry_run: bool = False,
    no_push: bool = False,
) -> str:
    """Build daily data package, call LLM, and send the report to DingTalk."""
    load_dotenv()
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Shanghai"))
    report_date = report_date or datetime.now(tz).date()
    top_deals_limit = int(os.getenv("ANALYSIS_TOP_DEALS_LIMIT", "20"))
    offsite_category = os.getenv("ANALYSIS_OFFSITE_CATEGORY", "fan")
    category_label = os.getenv("ANALYSIS_OFFSITE_CATEGORY_LABEL", "手持风扇")
    focus_brand = os.getenv("ANALYSIS_FOCUS_BRAND", "Diveblues")
    max_price = float(os.getenv("ANALYSIS_MAX_REASONABLE_PRICE", "200"))
    min_offsite_price = float(os.getenv("ANALYSIS_MIN_OFFSITE_PRICE", "5"))
    monitored_brands = load_monitored_brands()

    today_start_utc, today_end_utc = local_day_bounds_utc(report_date, tz)
    week_start_utc, _ = local_day_bounds_utc(report_date - timedelta(days=6), tz)

    repository = get_repository()
    slickdeals = repository.fetch_slickdeals_deals_between(
        today_start_utc,
        today_end_utc,
        category=offsite_category,
    )
    offsite_week = repository.fetch_slickdeals_deals_between(
        week_start_utc,
        today_end_utc,
        category=offsite_category,
    )

    report_payload = build_report_payload(
        report_date=report_date,
        tz=tz,
        slickdeals=slickdeals,
        top_deals_limit=top_deals_limit,
        monitored_brands=monitored_brands,
        max_reasonable_price=max_price,
        min_offsite_price=min_offsite_price,
        offsite_week=offsite_week,
        category_label=category_label,
        focus_brand=focus_brand,
    )

    if dry_run:
        output = json.dumps(report_payload, ensure_ascii=False, indent=2, default=str)
        print(output)
        return output

    prompt = render_prompt(report_payload)
    report_markdown = get_llm_client().complete_prompt(
        prompt,
        system="你是海外电商品牌的竞品数据分析助手。只基于输入数据生成简洁、可执行的中文日报。",
    )
    if not report_markdown:
        raise RuntimeError("LLM returned an empty report")

    if no_push:
        print(report_markdown)
        return report_markdown

    title = f"竞品监控日报 {report_date.isoformat()}"
    get_dingtalk_client().send_markdown(title=title, markdown=report_markdown)
    logger.info("Daily report sent to DingTalk")
    return report_markdown


def build_report_payload(
    *,
    report_date: date,
    tz: ZoneInfo,
    slickdeals: list[dict[str, Any]],
    top_deals_limit: int,
    monitored_brands: list[str],
    max_reasonable_price: float = 200,
    min_offsite_price: float = 5,
    offsite_week: list[dict[str, Any]] | None = None,
    category_label: str = "手持风扇",
    focus_brand: str = "Diveblues",
) -> dict[str, Any]:
    offsite_week = offsite_week or []

    return {
        "report_date": report_date.isoformat(),
        "timezone": str(tz),
        "category_label": category_label,
        "focus_brand": focus_brand,
        "generated_at": datetime.now(timezone.utc).astimezone(tz).isoformat(),
        "monitored_brands": monitored_brands,
        "summary_counts": {
            "offsite_deals_today": len(slickdeals),
        },
        "trends": summarize_offsite_trends(
            offsite_week=offsite_week,
            monitored_brands=monitored_brands,
            focus_brand=focus_brand,
            max_reasonable_price=max_reasonable_price,
        ),
        "competitor_candidates": summarize_competitor_candidates(
            offsite_rows=offsite_week,
            monitored_brands=monitored_brands,
        ),
        "offsite": summarize_offsite_deals(
            slickdeals,
            tz,
            top_deals_limit,
            monitored_brands,
            max_reasonable_price,
            min_offsite_price,
        ),
    }


def summarize_offsite_deals(
    deals: list[dict[str, Any]],
    tz: ZoneInfo,
    limit: int,
    monitored_brands: list[str],
    max_reasonable_price: float,
    min_offsite_price: float = 5,
) -> dict[str, Any]:
    # 类目相关性复核：对已入库数据再跑一次过滤，剔除抓取时规则尚未覆盖的历史噪音。
    relevant_deals = []
    dropped_irrelevant = 0
    for deal in deals:
        if is_relevant_to_category(
            deal.get("title") or "",
            deal.get("url") or "",
            deal.get("category") or "",
        ):
            relevant_deals.append(deal)
        else:
            dropped_irrelevant += 1
    if dropped_irrelevant:
        logger.info("Offsite relevance re-check: dropped %s irrelevant deal(s)", dropped_irrelevant)
    deals = relevant_deals

    # 价格下限：丢弃明显过低（疑似噪音/非竞品）的 Deal；价格缺失的不丢。
    filtered_deals = []
    dropped_low = 0
    for deal in deals:
        price = to_float_or_none(deal.get("price"))
        if price is not None and price < min_offsite_price:
            dropped_low += 1
            continue
        filtered_deals.append(deal)
    if dropped_low:
        logger.info("Offsite price floor: dropped %s deal(s) below $%.2f", dropped_low, min_offsite_price)
    deals = filtered_deals

    category_counts: dict[str, int] = defaultdict(int)
    brand_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    monitored_brand_set = {brand.lower(): brand for brand in monitored_brands}

    normalized_deals = []
    for deal in deals:
        category = deal.get("category") or "unknown"
        brand = deal.get("brand") or "unknown"
        source = deal.get("source") or "slickdeals"
        category_counts[category] += 1
        brand_counts[brand] += 1
        source_counts[source] += 1
        normalized_deals.append(normalize_deal(deal, tz, max_reasonable_price))

    normalized_deals.sort(
        key=lambda item: (
            item.get("thumbs_up") or 0,
            item.get("comments_count") or 0,
            item.get("price") is not None,
        ),
        reverse=True,
    )

    by_brand: dict[str, dict[str, Any]] = {}
    other_brands: dict[str, int] = defaultdict(int)
    for deal in normalized_deals:
        brand = deal.get("brand") or "unknown"
        canonical_brand = monitored_brand_set.get(str(brand).lower())
        if canonical_brand:
            bucket = by_brand.setdefault(
                canonical_brand,
                {
                    "brand": canonical_brand,
                    "deal_count": 0,
                    "price_min": None,
                    "price_max": None,
                    "discount_min": None,
                    "discount_max": None,
                    "deals": [],
                },
            )
            bucket["deal_count"] += 1
            bucket["deals"].append(deal)
            reasonable_price = reasonable_price_or_none(deal.get("price"), max_reasonable_price)
            bucket["price_min"] = min_optional(bucket["price_min"], reasonable_price)
            bucket["price_max"] = max_optional(bucket["price_max"], reasonable_price)
            bucket["discount_min"] = min_optional(bucket["discount_min"], deal.get("discount_pct"))
            bucket["discount_max"] = max_optional(bucket["discount_max"], deal.get("discount_pct"))
        else:
            other_brands[brand] += 1

    price_eligible_deals = [
        deal for deal in normalized_deals
        if reasonable_price_or_none(deal.get("price"), max_reasonable_price) is not None
    ]
    prices = [deal["price"] for deal in price_eligible_deals]
    lowest_price_deal = min(
        price_eligible_deals,
        key=lambda item: item["price"],
        default=None,
    )

    monitored_lower = {b.lower() for b in monitored_brands}

    def _source_summary(src: str) -> dict[str, Any]:
        rows = [d for d in normalized_deals if (d.get("source") or "slickdeals") == src]
        src_prices = [
            reasonable_price_or_none(d.get("price"), max_reasonable_price) for d in rows
        ]
        src_prices = [p for p in src_prices if p is not None]
        src_brands = {(d.get("brand") or "unknown") for d in rows} - {"unknown"}
        return {
            "deal_count": len(rows),
            "brand_count": len(src_brands),
            "price_min": min(src_prices) if src_prices else None,
            "price_max": max(src_prices) if src_prices else None,
        }

    def _competitor_rows(src: str, fields: list[str]) -> list[dict[str, Any]]:
        rows = [
            d for d in normalized_deals
            if (d.get("source") or "slickdeals") == src
            and (d.get("brand") or "").lower() in monitored_lower
        ]
        # 品牌归类，热度优先：Frontpage -> 点赞 -> 评论。
        rows.sort(key=lambda d: (
            str(d.get("brand") or "").lower(),
            not bool(d.get("is_frontpage")),
            -(d.get("thumbs_up") or 0),
            -(d.get("comments_count") or 0),
        ))
        return [{f: d.get(f) for f in fields} for d in rows]

    return {
        "source_counts": dict(sorted(source_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "brand_counts": dict(sorted(brand_counts.items())),
        "brand_count": len([brand for brand in brand_counts if brand != "unknown"]),
        "price_range": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "lowest_price_deal": lowest_price_deal,
            "max_reasonable_price": max_reasonable_price,
        },
        "monitored_brands": list(by_brand.values()),
        "other_brands": dict(sorted(other_brands.items())),
        "top_deals": normalized_deals[:limit],
        "summary_by_source": {
            "slickdeals": _source_summary("slickdeals"),
            "hip2save": _source_summary("hip2save"),
        },
        "slickdeals_competitor_deals": _competitor_rows(
            "slickdeals",
            ["brand", "title", "discount_pct", "price", "is_frontpage", "thumbs_up", "comments_count", "url"],
        ),
        "hip2save_competitor_deals": _competitor_rows(
            "hip2save",
            ["brand", "title", "discount_pct", "price", "comments_count", "posted_at", "url"],
        ),
    }


def normalize_deal(deal: dict[str, Any], tz: ZoneInfo, max_reasonable_price: float) -> dict[str, Any]:
    raw_price = to_float_or_none(deal.get("price"))
    report_price = reasonable_price_or_none(raw_price, max_reasonable_price)
    return {
        "deal_id": deal.get("deal_id"),
        "source": deal.get("source") or "slickdeals",
        "title": deal.get("title"),
        "brand": deal.get("brand"),
        "category": deal.get("category"),
        "price": report_price,
        "price_note": "价格超出合理范围，已排除" if raw_price is not None and report_price is None else None,
        "original_price": to_float_or_none(deal.get("original_price")),
        "discount_pct": to_float_or_none(deal.get("discount_pct")),
        "thumbs_up": to_int_or_none(deal.get("thumbs_up")),
        "comments_count": to_int_or_none(deal.get("comments_count")),
        "is_frontpage": deal.get("is_frontpage"),
        "posted_at": to_local_iso(deal.get("posted_at"), tz),
        "scraped_at": to_local_iso(deal.get("scraped_at"), tz),
        "url": deal.get("url"),
    }


def summarize_offsite_trends(
    *,
    offsite_week: list[dict[str, Any]],
    monitored_brands: list[str],
    focus_brand: str,
    max_reasonable_price: float,
) -> dict[str, Any]:
    focus_key = normalize_brand_key(focus_brand)
    monitored = {normalize_brand_key(brand): brand for brand in monitored_brands}
    by_brand: dict[str, dict[str, Any]] = {}

    for row in offsite_week:
        if not is_relevant_to_category(row.get("title") or "", row.get("url") or "", row.get("category") or ""):
            continue
        brand_key = normalize_brand_key(row.get("brand"))
        if brand_key not in monitored:
            continue
        brand = monitored[brand_key]
        bucket = by_brand.setdefault(
            brand,
            {
                "brand": brand,
                "deal_count": 0,
                "min_price": None,
                "max_discount": None,
            },
        )
        bucket["deal_count"] += 1
        price = reasonable_price_or_none(row.get("price"), max_reasonable_price)
        bucket["min_price"] = min_optional(bucket["min_price"], price)
        bucket["max_discount"] = max_optional(bucket["max_discount"], row.get("discount_pct"))

    focus_weekly = by_brand.get(monitored.get(focus_key))
    competitors = sorted(
        [value for brand, value in by_brand.items() if normalize_brand_key(brand) != focus_key],
        key=lambda item: item["deal_count"],
        reverse=True,
    )

    return {
        "window_days": 7,
        "focus_weekly": focus_weekly,
        "competitor_weekly": competitors[:5],
    }


def summarize_competitor_candidates(
    *,
    offsite_rows: list[dict[str, Any]],
    monitored_brands: list[str],
) -> list[dict[str, Any]]:
    monitored = {normalize_brand_key(brand) for brand in monitored_brands}
    buckets: dict[str, dict[str, Any]] = {}

    for row in offsite_rows:
        if not is_relevant_to_category(row.get("title") or "", row.get("url") or "", row.get("category") or ""):
            continue
        raw_brand = row.get("brand")
        brand = clean_candidate_brand(raw_brand)
        if not brand:
            brand = clean_candidate_brand(infer_brand_from_title(row.get("title") or ""))
        if not brand or normalize_brand_key(brand) in monitored:
            continue
        bucket = candidate_bucket(buckets, brand)
        bucket["offsite_count"] += 1
        bucket["sources"].add(row.get("source") or "slickdeals")
        day = parse_datetime(row.get("scraped_at"))
        if day:
            bucket["seen_days"].add(day.date().isoformat())
        bucket["heat_score"] += (to_int_or_none(row.get("thumbs_up")) or 0)
        bucket["heat_score"] += (to_int_or_none(row.get("comments_count")) or 0) * 2
        if row.get("is_frontpage") is True:
            bucket["heat_score"] += 50
        bucket["sample_title"] = bucket["sample_title"] or row.get("title")

    candidates = []
    for bucket in buckets.values():
        candidates.append(
            {
                "brand": bucket["brand"],
                "seen_days": len(bucket["seen_days"]),
                "source_count": len(bucket["sources"]),
                "offsite_count": bucket["offsite_count"],
                "heat_score": bucket["heat_score"],
                "sample_title": bucket["sample_title"],
            }
        )
    candidates.sort(
        key=lambda item: (
            item["seen_days"],
            item["source_count"],
            item["offsite_count"],
            item["heat_score"],
        ),
        reverse=True,
    )
    return candidates[:5]


def candidate_bucket(buckets: dict[str, dict[str, Any]], brand: str) -> dict[str, Any]:
    key = normalize_brand_key(brand)
    return buckets.setdefault(
        key,
        {
            "brand": brand,
            "seen_days": set(),
            "sources": set(),
            "offsite_count": 0,
            "heat_score": 0,
            "sample_title": None,
        },
    )


def clean_candidate_brand(value: Any) -> str | None:
    brand = str(value or "").strip()
    if not brand or brand.lower() == "unknown":
        return None
    if normalize_brand_key(brand) in GENERIC_BRAND_CANDIDATES:
        return None
    return brand


def render_prompt(report_payload: dict[str, Any]) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(report_payload, ensure_ascii=False, indent=2, default=str)
    return template.replace("{{DATA_JSON}}", data_json)


def local_day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_local_iso(value: Any, tz: ZoneInfo) -> str | None:
    parsed = parse_datetime(value)
    if not parsed:
        return None
    return parsed.astimezone(tz).isoformat()


def to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def min_optional(current: Any, candidate: Any) -> float | None:
    current_value = to_float_or_none(current)
    candidate_value = to_float_or_none(candidate)
    if current_value is None:
        return candidate_value
    if candidate_value is None:
        return current_value
    return min(current_value, candidate_value)


def max_optional(current: Any, candidate: Any) -> float | None:
    current_value = to_float_or_none(current)
    candidate_value = to_float_or_none(candidate)
    if current_value is None:
        return candidate_value
    if candidate_value is None:
        return current_value
    return max(current_value, candidate_value)


def reasonable_price_or_none(value: Any, max_reasonable_price: float) -> float | None:
    price = to_float_or_none(value)
    if price is None:
        return None
    if price <= 0 or price > max_reasonable_price:
        return None
    return price


def normalize_brand_key(value: Any) -> str:
    return str(value or "").strip().lower()


def load_monitored_brands() -> list[str]:
    if not BRAND_LIST_PATH.exists():
        return []
    brands = []
    for raw_line in BRAND_LIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            brands.append(line)
    return brands


def configure_logging() -> None:
    load_dotenv()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and send daily competitor report")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        help="Report date in local timezone, format YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print report payload only")
    parser.add_argument("--no-push", action="store_true", help="Generate report but do not send DingTalk")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    run(report_date=args.date, dry_run=args.dry_run, no_push=args.no_push)


if __name__ == "__main__":
    main()
