from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import keepa
from dotenv import load_dotenv

from utils.db import get_repository

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
VALID_CATEGORIES = {"fan", "hand_warmer"}
DEFAULT_BSR_CATEGORY_ID = "3303867011"
DEFAULT_BSR_CATEGORY_NAME = "Best Sellers in Personal Fans"


@dataclass(frozen=True)
class AsinConfig:
    asin: str
    category: str


def run(*, dry_run: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch Keepa product data and optionally insert Amazon snapshots."""
    load_dotenv()
    asin_configs = load_asin_configs(CONFIG_DIR / "asin_list.txt")
    if limit is not None:
        asin_configs = asin_configs[:limit]

    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        raise ValueError("KEEPA_API_KEY is required")

    domain = os.getenv("KEEPA_DOMAIN", "US")
    stats_days = int(os.getenv("KEEPA_STATS_DAYS", "1"))
    request_delay_seconds = float(os.getenv("KEEPA_REQUEST_DELAY_SECONDS", "3"))
    keepa_timeout_seconds = float(os.getenv("KEEPA_QUERY_TIMEOUT_SECONDS", "180"))
    fetch_buybox = parse_bool(os.getenv("KEEPA_FETCH_BUYBOX", "true"))
    bsr_category_id = os.getenv("KEEPA_BSR_CATEGORY_ID", DEFAULT_BSR_CATEGORY_ID).strip()
    bsr_category_name = os.getenv("KEEPA_BSR_CATEGORY_NAME", DEFAULT_BSR_CATEGORY_NAME).strip()

    api = keepa.Keepa(api_key, logging_level="INFO")
    snapshots: list[dict[str, Any]] = []

    for index, asin_config in enumerate(asin_configs, start=1):
        try:
            logger.info(
                "Fetching Keepa data asin=%s category=%s buybox=%s",
                asin_config.asin,
                asin_config.category,
                fetch_buybox,
            )
            product = fetch_product(
                api=api,
                asin=asin_config.asin,
                domain=domain,
                stats_days=stats_days,
                fetch_buybox=fetch_buybox,
                timeout_seconds=keepa_timeout_seconds,
            )
            if not product:
                logger.warning("No Keepa product returned for asin=%s", asin_config.asin)
                continue

            snapshot = product_to_snapshot(
                product,
                asin_config,
                bsr_category_id=bsr_category_id,
                bsr_category_name=bsr_category_name,
            )
            snapshots.append(snapshot)
            logger.info("Prepared Amazon snapshot asin=%s title=%r", snapshot["asin"], snapshot["title"])
        except Exception as exc:
            logger.error(
                "Failed to fetch Keepa data asin=%s: %s",
                asin_config.asin,
                sanitize_error(exc),
            )

        if index < len(asin_configs) and request_delay_seconds > 0:
            logger.info("Sleeping %.1f seconds before next Keepa request", request_delay_seconds)
            time.sleep(request_delay_seconds)

    logger.info("Collected %s Amazon snapshots", len(snapshots))

    if dry_run:
        print(json.dumps(snapshots, ensure_ascii=False, indent=2, default=str))
        return snapshots

    repository = get_repository()
    repository.insert_amazon_snapshots(snapshots)
    return snapshots


def check_key_status() -> dict[str, Any]:
    """Validate Keepa API key and return token status without querying a product."""
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        raise ValueError("KEEPA_API_KEY is required")

    try:
        api = keepa.Keepa(api_key, check_key=True, logging_level="INFO")
    except Exception as exc:
        raise RuntimeError(f"Keepa key check failed: {sanitize_error(exc)}") from None
    status = {
        "tokens_left": api.status.tokensLeft,
        "refill_in_ms": api.status.refillIn,
        "refill_rate": api.status.refillRate,
        "timestamp": api.status.timestamp,
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return status


def load_asin_configs(path: Path) -> list[AsinConfig]:
    configs: list[AsinConfig] = []
    for line_number, line in read_non_comment_lines(path):
        if "|" not in line:
            raise ValueError(f"{path}:{line_number} must use format: ASIN | category")

        asin, category = [part.strip() for part in line.split("|", maxsplit=1)]
        asin = asin.upper()
        if not asin:
            raise ValueError(f"{path}:{line_number} ASIN is empty")
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"{path}:{line_number} category must be one of {sorted(VALID_CATEGORIES)}"
            )
        configs.append(AsinConfig(asin=asin, category=category))

    if not configs:
        raise ValueError(f"No ASINs found in {path}")
    return configs


def read_non_comment_lines(path: Path) -> Iterable[tuple[int, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            yield line_number, line


def fetch_product(
    *,
    api: keepa.Keepa,
    asin: str,
    domain: str,
    stats_days: int,
    fetch_buybox: bool,
    timeout_seconds: float = 180.0,
) -> dict[str, Any] | None:
    # wait=True lets keepa-python pause when token balance is insufficient; add a wall-clock cap.
    products = run_with_timeout(
        api.query,
        timeout_seconds,
        asin,
        domain=domain,
        stats=stats_days,
        days=max(stats_days, 1),
        history=True,
        rating=True,
        buybox=fetch_buybox,
        wait=True,
        progress_bar=False,
    )
    return products[0] if products else None


def product_to_snapshot(
    product: dict[str, Any],
    asin_config: AsinConfig,
    *,
    bsr_category_id: str = DEFAULT_BSR_CATEGORY_ID,
    bsr_category_name: str = DEFAULT_BSR_CATEGORY_NAME,
) -> dict[str, Any]:
    stats = product.get("stats_parsed") or {}
    current_stats = stats.get("current") or {}
    data = product.get("data") or {}
    snapshot_at = datetime.now(timezone.utc).isoformat()

    price = first_number(
        current_stats.get("BUY_BOX_SHIPPING"),
        current_stats.get("NEW"),
        current_stats.get("AMAZON"),
        latest_series_value(data, "BUY_BOX_SHIPPING"),
        latest_series_value(data, "NEW"),
        latest_series_value(data, "AMAZON"),
    )
    buy_box_price = first_number(
        current_stats.get("BUY_BOX_SHIPPING"),
        latest_series_value(data, "BUY_BOX_SHIPPING"),
    )
    bsr = extract_category_bsr(product, bsr_category_id)
    if bsr is None and str(product.get("salesRankReference") or "") == str(bsr_category_id):
        bsr = first_int(
            current_stats.get("SALES"),
            latest_series_value(data, "SALES"),
        )
    if bsr is None:
        logger.warning(
            "No Keepa sales rank found for asin=%s category_id=%s category_name=%r",
            asin_config.asin,
            bsr_category_id,
            bsr_category_name,
        )
    rating = first_number(
        current_stats.get("RATING"),
        latest_series_value(data, "RATING"),
    )
    review_count = first_int(
        current_stats.get("COUNT_REVIEWS"),
        latest_series_value(data, "COUNT_REVIEWS"),
    )

    return {
        "asin": asin_config.asin,
        "brand": clean_text(product.get("brand")),
        "title": clean_text(product.get("title")),
        "category": asin_config.category,
        "price": price,
        "bsr": bsr,
        "bsr_category_id": bsr_category_id,
        "bsr_category_name": bsr_category_name,
        "rating": rating,
        "review_count": review_count,
        "buy_box_price": buy_box_price,
        "snapshot_at": snapshot_at,
    }


def extract_category_bsr(product: dict[str, Any], category_id: str) -> int | None:
    """Return latest positive BSR for the configured Amazon category node.

    Keepa's generic SALES field can point to a broader category. For this project
    we need the Personal Fans node, so use product["salesRanks"][category_id].
    """
    sales_ranks = product.get("salesRanks") or {}
    rank_history = sales_ranks.get(str(category_id))
    if rank_history is None:
        rank_history = sales_ranks.get(int(category_id)) if str(category_id).isdigit() else None
    return latest_rank_from_history(rank_history)


def latest_rank_from_history(rank_history: Any) -> int | None:
    if not rank_history:
        return None

    if isinstance(rank_history, dict):
        values = list(rank_history.values())
    else:
        values = list(rank_history)

    # Keepa rank histories are usually [time, rank, time, rank, ...].
    candidate_values = values[1::2] if len(values) >= 2 else values
    for value in reversed(candidate_values):
        rank = first_int(value)
        if rank and rank > 0:
            return rank
    return None


def latest_series_value(data: dict[str, Any], key: str) -> Any:
    values = data.get(key)
    if values is None:
        return None
    try:
        if len(values) == 0:
            return None
        return values[-1]
    except TypeError:
        return None


def first_number(*values: Any) -> float | None:
    for value in values:
        normalized = normalize_keepa_value(value)
        if normalized is None:
            continue
        try:
            number = float(normalized)
        except (TypeError, ValueError):
            continue
        if math.isnan(number) or number < 0:
            continue
        return round(number, 2)
    return None


def first_int(*values: Any) -> int | None:
    number = first_number(*values)
    return int(number) if number is not None else None


def normalize_keepa_value(value: Any) -> Any:
    if isinstance(value, tuple) and len(value) == 2:
        return value[1]
    if hasattr(value, "item"):
        return value.item()
    return value


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def run_with_timeout(func, timeout_seconds: float, /, *args, **kwargs):
    """给阻塞调用加 wall-clock 超时。超时抛 TimeoutError，避免 cron 无限卡住。"""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise TimeoutError(f"Keepa call exceeded {timeout_seconds:.0f}s timeout")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def sanitize_error(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"key=[A-Za-z0-9]+", "key=***", message)
    message = re.sub(r"/token/\?key=[A-Za-z0-9]+", "/token/?key=***", message)
    return message


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Amazon product snapshots from Keepa")
    parser.add_argument("--dry-run", action="store_true", help="Print snapshots without writing DB")
    parser.add_argument("--limit", type=int, default=None, help="Max ASINs to fetch")
    parser.add_argument(
        "--check-key",
        action="store_true",
        help="Validate KEEPA_API_KEY and print token status without querying ASINs",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    if args.check_key:
        check_key_status()
        return
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be greater than 0")
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
