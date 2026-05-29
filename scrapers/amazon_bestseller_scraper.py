from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import keepa
from dotenv import load_dotenv

from scrapers.keepa_fetcher import DEFAULT_BSR_CATEGORY_ID, DEFAULT_BSR_CATEGORY_NAME, load_asin_configs
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

    tracked_asins = {config.asin for config in load_asin_configs(CONFIG_DIR / "asin_list.txt")}
    api = keepa.Keepa(api_key, logging_level="INFO")
    logger.info(
        "Fetching Keepa best sellers category_id=%s category_name=%r limit=%s sublist=%s",
        category_id,
        category_name,
        requested_limit,
        sublist,
    )
    asin_list = api.best_sellers_query(
        category=category_id,
        rank_avg_range=rank_avg_range,
        variations=variations,
        sublist=sublist,
        domain=domain,
        wait=True,
    )

    snapshot_at = datetime.now(timezone.utc)
    rows = [
        {
            "category_id": category_id,
            "category_name": category_name,
            "rank": rank,
            "asin": asin.upper(),
            "is_tracked": asin.upper() in tracked_asins,
            "snapshot_date": snapshot_at.date().isoformat(),
            "snapshot_at": snapshot_at.isoformat(),
        }
        for rank, asin in enumerate(asin_list[:requested_limit], start=1)
    ]
    logger.info("Collected %s Amazon best-seller rows", len(rows))

    if dry_run:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        return rows

    repository = get_repository()
    repository.upsert_amazon_bestsellers(rows)
    return rows


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
