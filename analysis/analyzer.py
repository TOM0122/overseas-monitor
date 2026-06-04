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

from utils.db import get_repository
from utils.dingtalk import get_dingtalk_client
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "daily_report.md"
BRAND_LIST_PATH = PROJECT_ROOT / "config" / "brand_list.txt"


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
    min_offsite_price = float(os.getenv("ANALYSIS_MIN_OFFSITE_PRICE", "3"))
    bsr_category_id = os.getenv("KEEPA_BSR_CATEGORY_ID", "3303867011")
    bsr_category_name = os.getenv("KEEPA_BSR_CATEGORY_NAME", "Best Sellers in Personal Fans")
    rank_up_threshold = int(os.getenv("BESTSELLER_RANK_UP_THRESHOLD", "10"))
    monitored_brands = load_monitored_brands()

    today_start_utc, today_end_utc = local_day_bounds_utc(report_date, tz)
    yesterday_start_utc, _ = local_day_bounds_utc(report_date - timedelta(days=1), tz)

    repository = get_repository()
    slickdeals = repository.fetch_slickdeals_deals_between(
        today_start_utc,
        today_end_utc,
        category=offsite_category,
    )
    amazon_today = repository.fetch_amazon_snapshots_between(today_start_utc, today_end_utc)
    amazon_yesterday = repository.fetch_amazon_snapshots_between(
        yesterday_start_utc,
        today_start_utc,
    )
    bestsellers_today = repository.fetch_amazon_bestsellers_between(
        today_start_utc,
        today_end_utc,
        category_id=bsr_category_id,
    )
    bestsellers_yesterday = repository.fetch_amazon_bestsellers_between(
        yesterday_start_utc,
        today_start_utc,
        category_id=bsr_category_id,
    )

    report_payload = build_report_payload(
        report_date=report_date,
        tz=tz,
        slickdeals=slickdeals,
        amazon_today=amazon_today,
        amazon_yesterday=amazon_yesterday,
        top_deals_limit=top_deals_limit,
        monitored_brands=monitored_brands,
        max_reasonable_price=max_price,
        min_offsite_price=min_offsite_price,
        bsr_category_id=bsr_category_id,
        bsr_category_name=bsr_category_name,
        bestsellers_today=bestsellers_today,
        bestsellers_yesterday=bestsellers_yesterday,
        rank_up_threshold=rank_up_threshold,
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
    amazon_today: list[dict[str, Any]],
    amazon_yesterday: list[dict[str, Any]],
    top_deals_limit: int,
    monitored_brands: list[str],
    max_reasonable_price: float = 200,
    min_offsite_price: float = 3,
    bsr_category_id: str = "3303867011",
    bsr_category_name: str = "Best Sellers in Personal Fans",
    bestsellers_today: list[dict[str, Any]] | None = None,
    bestsellers_yesterday: list[dict[str, Any]] | None = None,
    rank_up_threshold: int = 10,
    category_label: str = "手持风扇",
    focus_brand: str = "Diveblues",
) -> dict[str, Any]:
    bsr_today = filter_bsr_snapshots(amazon_today, bsr_category_id)
    bsr_yesterday = filter_bsr_snapshots(amazon_yesterday, bsr_category_id)
    today_latest = latest_snapshot_by_asin(bsr_today)
    yesterday_latest = latest_snapshot_by_asin(bsr_yesterday)

    bsr_items = []
    for asin, today in sorted(today_latest.items()):
        yesterday = yesterday_latest.get(asin)
        bsr_items.append(build_bsr_item(today, yesterday, tz))

    return {
        "report_date": report_date.isoformat(),
        "timezone": str(tz),
        "category_label": category_label,
        "focus_brand": focus_brand,
        "generated_at": datetime.now(timezone.utc).astimezone(tz).isoformat(),
        "monitored_brands": monitored_brands,
        "bsr_category": {
            "id": bsr_category_id,
            "name": bsr_category_name,
        },
        "summary_counts": {
            "offsite_deals_today": len(slickdeals),
            "amazon_snapshots_today": len(amazon_today),
            "amazon_bsr_snapshots_today": len(bsr_today),
            "amazon_bsr_asins_today": len(today_latest),
            "amazon_bestsellers_today": len(bestsellers_today or []),
            "amazon_asins_with_yesterday_baseline": sum(
                1 for asin in today_latest if asin in yesterday_latest
            ),
        },
        "bsr_monitor": summarize_bsr_monitor(
            bsr_items,
            bestsellers_today or [],
            bestsellers_yesterday or [],
            focus_brand,
        ),
        "bestseller_monitor": summarize_bestseller_rankings(
            bestsellers_today or [],
            bestsellers_yesterday or [],
            rank_up_threshold=rank_up_threshold,
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


def filter_bsr_snapshots(snapshots: list[dict[str, Any]], bsr_category_id: str) -> list[dict[str, Any]]:
    filtered = []
    for snapshot in snapshots:
        snapshot_category_id = snapshot.get("bsr_category_id")
        if str(snapshot_category_id or "") == str(bsr_category_id):
            filtered.append(snapshot)
    return filtered


def summarize_offsite_deals(
    deals: list[dict[str, Any]],
    tz: ZoneInfo,
    limit: int,
    monitored_brands: list[str],
    max_reasonable_price: float,
    min_offsite_price: float = 3,
) -> dict[str, Any]:
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
        "posted_at": to_local_iso(deal.get("posted_at"), tz),
        "scraped_at": to_local_iso(deal.get("scraped_at"), tz),
        "url": deal.get("url"),
    }


def latest_snapshot_by_asin(snapshots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        asin = snapshot.get("asin")
        if not asin:
            continue
        current_time = parse_datetime(snapshot.get("snapshot_at")) or datetime.min.replace(tzinfo=timezone.utc)
        previous_time = parse_datetime(latest.get(asin, {}).get("snapshot_at")) if asin in latest else None
        if previous_time is None or current_time > previous_time:
            latest[asin] = snapshot
    return latest


def build_bsr_item(
    today: dict[str, Any],
    yesterday: dict[str, Any] | None,
    tz: ZoneInfo,
) -> dict[str, Any]:
    current_bsr = to_int_or_none(today.get("bsr"))
    yesterday_bsr = to_int_or_none(yesterday.get("bsr")) if yesterday else None
    bsr_abs = diff(current_bsr, yesterday_bsr)
    return {
        "source": "amazon_snapshots",
        "asin": today.get("asin"),
        "brand": today.get("brand"),
        "title": today.get("title"),
        "category": today.get("category"),
        "snapshot_at": to_local_iso(today.get("snapshot_at"), tz),
        "current_rank": current_bsr,
        "yesterday_rank": yesterday_bsr,
        "rank_change": bsr_abs,
        "rank_change_display": format_rank_change(bsr_abs),
        "current_bsr": current_bsr,
        "yesterday_bsr": yesterday_bsr,
        "bsr_change_abs": bsr_abs,
        "data_status": "ok" if current_bsr is not None and yesterday_bsr is not None else "数据缺失",
        "missing_fields": {
            "today_bsr": current_bsr is None,
            "yesterday_bsr": yesterday_bsr is None,
        },
        "yesterday_snapshot_at": to_local_iso(yesterday.get("snapshot_at"), tz) if yesterday else None,
    }


def summarize_bsr_monitor(
    snapshot_items: list[dict[str, Any]],
    bestsellers_today: list[dict[str, Any]],
    bestsellers_yesterday: list[dict[str, Any]],
    focus_brand: str,
) -> dict[str, Any]:
    # 优先使用 amazon_bestsellers 的类目榜单 rank，和 Amazon Best Sellers 页面口径一致。
    items = build_bestseller_bsr_items(bestsellers_today, bestsellers_yesterday)
    if items:
        bestseller_asins = {normalize_asin(item.get("asin")) for item in items}
        items.extend(
            item for item in snapshot_items
            if normalize_asin(item.get("asin")) not in bestseller_asins
        )
    else:
        items = snapshot_items
    return summarize_bsr(items, focus_brand)


def build_bestseller_bsr_items(
    today_rows: list[dict[str, Any]],
    yesterday_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    today_latest = latest_bestseller_by_asin(today_rows)
    yesterday_latest = latest_bestseller_by_asin(yesterday_rows)
    tracked_today = [
        row for row in today_latest.values()
        if row.get("is_tracked") is True
    ]
    tracked_today.sort(key=lambda row: to_int_or_none(row.get("rank")) or 999999)

    items: list[dict[str, Any]] = []
    for row in tracked_today:
        asin = str(row.get("asin") or "").upper()
        previous = yesterday_latest.get(asin)
        current_rank = to_int_or_none(row.get("rank"))
        yesterday_rank = to_int_or_none(previous.get("rank")) if previous else None
        rank_change = diff(current_rank, yesterday_rank)
        items.append(
            {
                "source": "amazon_bestsellers",
                "asin": row.get("asin"),
                "brand": row.get("brand"),
                "title": row.get("title"),
                "snapshot_at": row.get("snapshot_at"),
                "current_rank": current_rank,
                "yesterday_rank": yesterday_rank,
                "rank_change": rank_change,
                "rank_change_display": format_rank_change(rank_change),
                "current_bsr": current_rank,
                "yesterday_bsr": yesterday_rank,
                "bsr_change_abs": rank_change,
                "data_status": "ok" if current_rank is not None and yesterday_rank is not None else "数据缺失",
                "missing_fields": {
                    "today_rank": current_rank is None,
                    "yesterday_rank": yesterday_rank is None,
                },
            }
        )
    return items


def _bsr_sort_key(item: dict[str, Any]) -> tuple[bool, int]:
    rank = to_int_or_none(item.get("current_rank"))
    # 有排名的在前并按升序，排名缺失的统一排到最后。
    return (rank is None, rank if rank is not None else 0)


def summarize_bsr(items: list[dict[str, Any]], focus_brand: str) -> dict[str, Any]:
    focus_key = normalize_brand_key(focus_brand)
    focus = [item for item in items if normalize_brand_key(item.get("brand")) == focus_key]
    competitors = [item for item in items if normalize_brand_key(item.get("brand")) != focus_key]
    focus.sort(key=_bsr_sort_key)
    competitors.sort(key=_bsr_sort_key)
    return {"focus": focus, "competitors": competitors}


def summarize_bestseller_rankings(
    today_rows: list[dict[str, Any]],
    yesterday_rows: list[dict[str, Any]],
    *,
    rank_up_threshold: int,
) -> dict[str, Any]:
    today_latest = latest_bestseller_by_asin(today_rows)
    yesterday_latest = latest_bestseller_by_asin(yesterday_rows)

    top_today = sorted(today_latest.values(), key=lambda row: to_int_or_none(row.get("rank")) or 999999)
    tracked_today = [normalize_bestseller_row(row) for row in top_today if row.get("is_tracked") is True]
    untracked_top = [normalize_bestseller_row(row) for row in top_today if row.get("is_tracked") is not True]

    new_entries = [
        normalize_bestseller_row(row)
        for asin, row in today_latest.items()
        if asin not in yesterday_latest
    ]
    new_entries.sort(key=lambda row: row.get("rank") or 999999)

    rank_gainers = []
    rank_droppers = []
    for asin, row in today_latest.items():
        previous = yesterday_latest.get(asin)
        if not previous:
            continue
        current_rank = to_int_or_none(row.get("rank"))
        previous_rank = to_int_or_none(previous.get("rank"))
        if current_rank is None or previous_rank is None:
            continue
        rank_change = previous_rank - current_rank
        item = normalize_bestseller_row(row)
        item["yesterday_rank"] = previous_rank
        item["rank_change"] = rank_change
        if rank_change >= rank_up_threshold:
            rank_gainers.append(item)
        elif rank_change <= -rank_up_threshold:
            rank_droppers.append(item)

    rank_gainers.sort(key=lambda row: row["rank_change"], reverse=True)
    rank_droppers.sort(key=lambda row: row["rank_change"])

    return {
        "rank_up_threshold": rank_up_threshold,
        "today_count": len(top_today),
        "yesterday_count": len(yesterday_latest),
        "tracked_in_top": tracked_today,
        "new_entries": new_entries[:20],
        "rank_gainers": rank_gainers[:20],
        "rank_droppers": rank_droppers[:20],
        "untracked_top": untracked_top[:20],
    }


def latest_bestseller_by_asin(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        asin = str(row.get("asin") or "").upper()
        if not asin:
            continue
        current_time = parse_datetime(row.get("snapshot_at")) or datetime.min.replace(tzinfo=timezone.utc)
        previous_time = parse_datetime(latest.get(asin, {}).get("snapshot_at")) if asin in latest else None
        if previous_time is None or current_time > previous_time:
            latest[asin] = row
    return latest


def normalize_bestseller_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "asin": row.get("asin"),
        "rank": to_int_or_none(row.get("rank")),
        "is_tracked": row.get("is_tracked"),
        "brand": row.get("brand"),
        "title": row.get("title"),
        "snapshot_at": row.get("snapshot_at"),
    }


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


def diff(current: Any, previous: Any) -> float | None:
    current_number = to_float_or_none(current)
    previous_number = to_float_or_none(previous)
    if current_number is None or previous_number is None:
        return None
    return round(current_number - previous_number, 4)


def format_rank_change(change_abs: Any) -> str:
    change = to_float_or_none(change_abs)
    if change is None:
        return "数据缺失"
    if change == 0:
        return "持平"
    if float(change).is_integer():
        change_text = f"{int(change):+d}"
    else:
        change_text = f"{change:+g}"
    return f"{change_text} 名"


def pct_change(current: Any, previous: Any) -> float | None:
    current_number = to_float_or_none(current)
    previous_number = to_float_or_none(previous)
    if current_number is None or previous_number in (None, 0):
        return None
    return round((current_number - previous_number) / previous_number * 100, 2)


def bsr_direction(change_abs: float | None) -> str | None:
    if change_abs is None:
        return None
    if change_abs < 0:
        return "排名上升"
    if change_abs > 0:
        return "排名下降"
    return "持平"


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


def normalize_asin(value: Any) -> str:
    return str(value or "").strip().upper()


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
