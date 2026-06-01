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
    load_asin_configs,
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
    request_delay_seconds = float(os.getenv("KEEPA_REQUEST_DELAY_SECONDS", "3"))

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
    asin_list = api.best_sellers_query(
        category=category_id,
        rank_avg_range=rank_avg_range,
        variations=variations,
        sublist=sublist,
        domain=domain,
        wait=True,
    )

    ranked_asins = [asin.upper() for asin in asin_list[:requested_limit]]
    metadata = fetch_bestseller_metadata(
        api,
        ranked_asins,
        domain=domain,
        enabled=enrich_brands,
        limit=enrich_limit,
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


def fetch_bestseller_metadata(
    api: "keepa.Keepa",
    asins: list[str],
    *,
    domain: str,
    enabled: bool,
    limit: int,
) -> dict[str, dict[str, str | None]]:
    """批量获取榜单 ASIN 的 brand/title。尽力而为：失败返回空 dict。"""
    if not enabled or not asins or limit <= 0:
        return {}
    targets = asins[:limit]
    try:
        products = api.query(
            targets,
            domain=domain,
            history=False,
            rating=False,
            buybox=False,
            wait=True,
            progress_bar=False,
        )
    except Exception as exc:
        logger.warning("Bestseller brand enrichment failed: %s", exc)
        return {}

    metadata: dict[str, dict[str, str | None]] = {}
    for product in products or []:
        asin = str(product.get("asin") or "").upper()
        if not asin:
            continue
        metadata[asin] = {
            "brand": clean_text(product.get("brand")),
            "title": clean_text(product.get("title")),
        }
    logger.info("Enriched %s/%s best-seller ASINs with brand/title", len(metadata), len(targets))
    return metadata


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
