from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import keepa
from dotenv import load_dotenv

from scrapers.keepa_fetcher import (
    DEFAULT_BSR_CATEGORY_ID,
    DEFAULT_BSR_CATEGORY_NAME,
    clean_text,
    first_number,
    latest_series_value,
    load_asin_configs,
    run_with_timeout,
)
from utils.db import get_repository

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


def run(*, dry_run: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch Amazon category best-seller ASIN rankings through Keepa."""
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        raise ValueError("KEEPA_API_KEY is required")

    domain = os.getenv("KEEPA_DOMAIN", "US")
    category_id = os.getenv("KEEPA_BSR_CATEGORY_ID", DEFAULT_BSR_CATEGORY_ID).strip()
    category_name = os.getenv("KEEPA_BSR_CATEGORY_NAME", DEFAULT_BSR_CATEGORY_NAME).strip()
    requested_limit = limit or int(os.getenv("KEEPA_BESTSELLER_LIMIT", "100"))
    rank_avg_range = int(os.getenv("KEEPA_BESTSELLER_RANK_AVG_RANGE", "0"))
    sublist = parse_bool(os.getenv("KEEPA_BESTSELLER_SUBLIST", "true"))
    variations = parse_bool(os.getenv("KEEPA_BESTSELLER_VARIATIONS", "false"))
    enrich_brands = parse_bool(os.getenv("KEEPA_BESTSELLER_ENRICH", "true"))
    enrich_limit = int(os.getenv("KEEPA_BESTSELLER_ENRICH_LIMIT", str(requested_limit)))
    enrich_prices = parse_bool(os.getenv("KEEPA_BESTSELLER_PRICE_ENRICH", "true"))
    price_limit = int(os.getenv("KEEPA_BESTSELLER_PRICE_LIMIT", "30"))
    request_delay_seconds = float(os.getenv("KEEPA_REQUEST_DELAY_SECONDS", "3"))
    keepa_timeout_seconds = float(os.getenv("KEEPA_QUERY_TIMEOUT_SECONDS", "180"))

    tracked_asins = {config.asin for config in load_asin_configs(CONFIG_DIR / "asin_list.txt")}
    api = keepa.Keepa(api_key, logging_level="INFO")
    logger.info(
        "Fetching Keepa best sellers category_id=%s category_name=%r limit=%s sublist=%s request_delay=%ss",
        category_id,
        category_name,
        requested_limit,
        sublist,
        request_delay_seconds,
    )
    asin_list = run_with_timeout(
        api.best_sellers_query,
        keepa_timeout_seconds,
        category=category_id,
        rank_avg_range=rank_avg_range,
        variations=variations,
        sublist=sublist,
        domain=domain,
        wait=True,
    )

    ranked_asins = [asin.upper() for asin in asin_list[:requested_limit]]
    metadata = fetch_bestseller_enrichment(
        api,
        ranked_asins,
        domain=domain,
        enrich_brands=enrich_brands,
        brand_limit=enrich_limit,
        enrich_prices=enrich_prices,
        price_limit=price_limit,
        timeout_seconds=keepa_timeout_seconds,
    )

    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Shanghai"))
    snapshot_at = datetime.now(timezone.utc)
    snapshot_date = snapshot_at.astimezone(tz).date().isoformat()
    rows = [
        {
            "category_id": category_id,
            "category_name": category_name,
            "rank": rank,
            "asin": asin,
            "is_tracked": asin in tracked_asins,
            "brand": metadata.get(asin, {}).get("brand"),
            "title": metadata.get(asin, {}).get("title"),
            "price": metadata.get(asin, {}).get("price"),
            "buy_box_price": metadata.get(asin, {}).get("buy_box_price"),
            "price_source": metadata.get(asin, {}).get("price_source"),
            "snapshot_date": snapshot_date,
            "snapshot_at": snapshot_at.isoformat(),
        }
        for rank, asin in enumerate(ranked_asins, start=1)
    ]
    logger.info("Collected %s Amazon best-seller rows", len(rows))

    if dry_run:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return rows

    repository = get_repository()
    repository.upsert_amazon_bestsellers(rows)
    return rows


def fetch_bestseller_enrichment(
    api: "keepa.Keepa",
    asins: list[str],
    *,
    domain: str,
    enrich_brands: bool,
    brand_limit: int,
    enrich_prices: bool,
    price_limit: int,
    timeout_seconds: float = 180.0,
) -> dict[str, dict[str, Any]]:
    """批量获取榜单 ASIN 的 brand/title 与 Top30 价格。尽力而为：失败返回空 dict。"""
    target_count = max(brand_limit if enrich_brands else 0, price_limit if enrich_prices else 0)
    if not asins or target_count <= 0:
        return {}
    targets = asins[:target_count]
    try:
        products = run_with_timeout(
            api.query,
            timeout_seconds,
            targets,
            domain=domain,
            stats=1,
            history=False,
            rating=False,
            buybox=enrich_prices,
            wait=True,
            progress_bar=False,
        )
    except Exception as exc:
        logger.warning("Bestseller enrichment failed: %s", exc)
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    brand_targets = set(asins[:brand_limit]) if enrich_brands else set()
    price_targets = set(asins[:price_limit]) if enrich_prices else set()
    for product in products or []:
        asin = str(product.get("asin") or "").upper()
        if not asin:
            continue
        item: dict[str, Any] = {}
        if asin in brand_targets:
            item["brand"] = clean_text(product.get("brand"))
            item["title"] = clean_text(product.get("title"))
        if asin in price_targets:
            price_item = extract_bestseller_price(product)
            item.update(price_item)
        metadata[asin] = item
    logger.info(
        "Enriched %s/%s best-seller ASINs with metadata price_limit=%s brand_limit=%s",
        len(metadata),
        len(targets),
        price_limit if enrich_prices else 0,
        brand_limit if enrich_brands else 0,
    )
    return metadata


def extract_bestseller_price(product: dict[str, Any]) -> dict[str, Any]:
    stats = product.get("stats_parsed") or {}
    current_stats = stats.get("current") or {}
    data = product.get("data") or {}
    buy_box_price = first_number(
        current_stats.get("BUY_BOX_SHIPPING"),
        latest_series_value(data, "BUY_BOX_SHIPPING"),
    )
    new_price = first_number(
        current_stats.get("NEW"),
        latest_series_value(data, "NEW"),
    )
    amazon_price = first_number(
        current_stats.get("AMAZON"),
        latest_series_value(data, "AMAZON"),
    )
    if buy_box_price is not None:
        return {"price": buy_box_price, "buy_box_price": buy_box_price, "price_source": "buy_box"}
    if new_price is not None:
        return {"price": new_price, "buy_box_price": None, "price_source": "new"}
    if amazon_price is not None:
        return {"price": amazon_price, "buy_box_price": None, "price_source": "amazon"}
    return {"price": None, "buy_box_price": None, "price_source": None}


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def configure_logging() -> None:
    load_dotenv()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Amazon category best-seller rankings via Keepa")
    parser.add_argument("--limit", type=int, default=None, help="Max best-seller ASINs to store")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing DB")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be greater than 0")
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
